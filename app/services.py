# === app/services.py ===
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


# 1) Fetch archives metadata
def fetch_archives(
    username: str,
    months_to_include: Optional[Set[str]] = None,
) -> List[Tuple[str, Dict[str, Any]]]:
    url = f"https://api.chess.com/pub/player/{username}/games/archives"
    resp = httpx.get(url)
    resp.raise_for_status()
    archive_urls = resp.json().get("archives", [])
    results = []
    for archive_url in archive_urls:
        parts = archive_url.rstrip("/").split("/")
        month = f"{parts[-2]}-{parts[-1]}"
        # skip any month we don't want
        if months_to_include and month not in months_to_include:
            continue
        month_json = httpx.get(archive_url).json()
        logger.info(f"Fetched archive {month}")
        results.append((month, month_json))
    return results


# 2) Unpack one month into Games
def unpack_archive(archive_id: str):
    with Session(engine) as session:
        arc = session.get(ArchiveMonth, archive_id)
        if not arc or arc.processed:
            return

        games = arc.raw_json.get("games", [])
        success = 0
        for obj in games:
            try:
                # --- extract headers as before ---
                headers = obj.get("pgn", "").split("\n\n")[0]

                def hv(name):
                    for l in headers.splitlines():
                        if l.startswith(f"[{name} "):
                            return l.split('"')[1]
                    return ""

                # extract ECOUrl
                eco_url = hv("ECOUrl")

                dt = datetime.strptime(
                    f"{hv('UTCDate')} {hv('UTCTime')}", "%Y.%m.%d %H:%M:%S"
                )
                user = arc.username.lower()
                white, black = obj.get("white", {}), obj.get("black", {})
                me, opponent = (
                    (white, black)
                    if white.get("username", "").lower() == user
                    else (black, white)
                )
                result = me.get("result", "")
                opp_res = opponent.get("result", "")

                game = Game(
                    username=arc.username,
                    game_uuid=obj["uuid"],
                    url=obj.get("url", ""),
                    played_at=dt,
                    time_class=obj.get("time_class", ""),
                    time_control=obj.get("time_control", ""),
                    result=result,
                    eco=hv("ECO"),
                    eco_url=eco_url,
                    opponent_result=opp_res,
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

        # finally mark this month done
        arc.processed = True
        session.add(arc)
        session.commit()
        logger.info(f"Unpacked {success}/{len(games)} games for {arc.month}")


# 3) Run the sync job
# (this is called in the background task)
def run_sync_job(job_id: str):
    from sqlalchemy.exc import SQLAlchemyError

    with Session(engine) as session:
        job = session.get(Job, job_id)
        job.status = "running"
        job.updated_at = datetime.now(timezone.utc)
        session.add(job)
        session.commit()

        # only pull current + previous month
        now = datetime.now(timezone.utc)
        current_month = now.strftime("%Y-%m")
        prev_month = (now.replace(day=1) - timedelta(days=1)).strftime("%Y-%m")
        months = fetch_archives(
            job.username,
            months_to_include={current_month, prev_month},
        )
        # ⚙️ initialize progress counters
        job.total = len(months)
        job.processed = 0
        session.add(job)
        session.commit()

        try:
            for month_str, raw in months:
                # 1) upsert ArchiveMonth
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
                elif month_str == current_month:
                    arc.raw_json = raw
                    arc.fetched_at = datetime.now(timezone.utc)
                    arc.processed = False

                session.add(arc)
                session.commit()  # persist the raw archive

                # 2) unpack games immediately
                unpack_archive(arc.id)

                # 3) bump job progress
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
