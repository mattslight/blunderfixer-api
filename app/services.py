import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Set, Tuple

import httpx
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, select

from app.db import engine
from app.models import ArchiveMonth, Game, Job

logger = logging.getLogger("blunderfixer.services")
logging.basicConfig(level=logging.INFO)


def fetch_archives(
    username: str,
    months_to_include: Optional[Set[str]] = None,
) -> List[Tuple[str, Dict[str, Any]]]:
    """
    Fetch the list of Chess.com archive URLs for a user and return only those months in `months_to_include`.
    """
    url = f"https://api.chess.com/pub/player/{username}/games/archives"
    resp = httpx.get(url)
    resp.raise_for_status()
    archive_urls = resp.json().get("archives", [])
    results = []
    for archive_url in archive_urls:
        parts = archive_url.rstrip("/").split("/")
        month = f"{parts[-2]}-{parts[-1]}"
        if months_to_include and month not in months_to_include:
            continue
        month_json = httpx.get(archive_url).json()
        logger.info(f"Fetched archive {month}")
        results.append((month, month_json))
    return results


def unpack_archive(archive_id: str):
    """
    Unpack a single ArchiveMonth record into individual Game rows using the new player/white/black fields.
    """
    with Session(engine) as session:
        arc = session.get(ArchiveMonth, archive_id)
        if not arc or arc.processed:
            return

        games = arc.raw_json.get("games", [])
        success = 0
        for obj in games:
            try:
                # Extract PGN headers
                headers = obj.get("pgn", "").split("\n\n")[0]

                def hv(name: str) -> str:
                    for l in headers.splitlines():
                        if l.startswith(f"[{name} "):
                            return l.split('"')[1]
                    return ""

                # Player info
                white = obj.get("white", {})
                black = obj.get("black", {})

                # Timestamps
                dt = datetime.strptime(
                    f"{hv('UTCDate')} {hv('UTCTime')}", "%Y.%m.%d %H:%M:%S"
                )
                end_time = datetime.fromtimestamp(obj.get("end_time", 0), timezone.utc)

                # Build and insert the Game row
                game = Game(
                    game_uuid=obj.get("uuid", ""),
                    url=obj.get("url", ""),
                    played_at=dt,
                    end_time=end_time,
                    time_class=obj.get("time_class", ""),
                    time_control=obj.get("time_control", ""),
                    white_username=white.get("username"),
                    white_rating=int(white.get("rating", 0)),
                    white_result=white.get("result", ""),
                    black_username=black.get("username"),
                    black_rating=int(black.get("rating", 0)),
                    black_result=black.get("result", ""),
                    eco=hv("ECO"),
                    eco_url=hv("ECOUrl"),
                    pgn=obj.get("pgn", ""),
                    raw=obj,
                )
                session.add(game)
                session.commit()
                success += 1
            except IntegrityError:
                session.rollback()
                logger.info(f"⏭️ Skipping duplicate game {obj.get('uuid')}")
            except Exception as e:
                session.rollback()
                logger.error(f"❌ Failed to insert game {obj.get('uuid')}: {e}")

        # Mark the archive as processed
        arc.processed = True
        session.add(arc)
        session.commit()
        logger.info(f"Unpacked {success}/{len(games)} games for {arc.month}")


def run_sync_job(job_id: str):
    from sqlalchemy.exc import SQLAlchemyError

    with Session(engine) as session:
        job = session.get(Job, job_id)
        job.status = "running"
        job.updated_at = datetime.now(timezone.utc)
        session.add(job)
        session.commit()

        # Only sync current and previous month
        now = datetime.now(timezone.utc)
        current_month = now.strftime("%Y-%m")
        prev_month = (now.replace(day=1) - timedelta(days=1)).strftime("%Y-%m")
        months = fetch_archives(
            job.username, months_to_include={current_month, prev_month}
        )

        # Initialize progress
        job.total = len(months)
        job.processed = 0
        session.add(job)
        session.commit()

        try:
            for month_str, raw in months:
                # Upsert ArchiveMonth
                arc = session.exec(
                    select(ArchiveMonth)
                    .where(ArchiveMonth.username == job.username)
                    .where(ArchiveMonth.month == month_str)
                ).first()
                if not arc:
                    arc = ArchiveMonth(
                        username=job.username,
                        month=month_str,
                        raw_json=raw,
                        fetched_at=datetime.now(timezone.utc),
                        processed=False,
                    )
                else:
                    arc.raw_json = raw
                    arc.fetched_at = datetime.now(timezone.utc)
                    arc.processed = False

                session.add(arc)
                session.commit()

                # Immediately unpack
                unpack_archive(arc.id)

                # Bump progress
                job.processed += 1
                job.updated_at = datetime.now(timezone.utc)
                session.add(job)
                session.commit()

            job.status = "complete"
            job.updated_at = datetime.now(timezone.utc)
            session.add(job)
            session.commit()

        except SQLAlchemyError as e:
            session.rollback()
            job.status = "failed"
            job.error = str(e)
            job.updated_at = datetime.now(timezone.utc)
            session.add(job)
            session.commit()
            raise
