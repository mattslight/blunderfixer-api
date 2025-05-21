# === app/services.py ===
import logging
from datetime import datetime
from typing import Any, Dict, List, Tuple

import httpx
from sqlmodel import Session, select

from app.db import engine
from app.models import ArchiveMonth, Game

logger = logging.getLogger("blunderfixer.services")
logging.basicConfig(level=logging.INFO)


# 1) Fetch archives metadata
def fetch_archives(username: str) -> List[Tuple[str, Dict[str, Any]]]:
    url = f"https://api.chess.com/pub/player/{username}/games/archives"
    resp = httpx.get(url)
    resp.raise_for_status()
    archive_urls = resp.json().get("archives", [])
    results = []
    for archive_url in archive_urls:
        parts = archive_url.rstrip("/").split("/")
        month = f"{parts[-2]}-{parts[-1]}"
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
        for obj in games:
            # Parse key headers
            headers = obj.get("pgn", "").split("\n\n")[0]

            def hv(name):
                for l in headers.splitlines():
                    if l.startswith(f"[{name} "):
                        return l.split('"')[1]
                return ""

            date = hv("UTCDate")
            time = hv("UTCTime")
            played_at = datetime.strptime(f"{date} {time}", "%Y.%m.%d %H:%M:%S")
            user = arc.username.lower()
            white, black = obj.get("white", {}), obj.get("black", {})
            result = (
                white if white.get("username", "").lower() == user else black
            ).get("result", "")
            game = Game(
                username=arc.username,
                game_uuid=obj.get("uuid", ""),
                url=obj.get("url", ""),
                played_at=played_at,
                time_class=obj.get("time_class", ""),
                time_control=obj.get("time_control", ""),
                result=result,
                eco=hv("ECO"),
                pgn=obj.get("pgn", ""),
                raw=obj,
            )
            session.add(game)
        # mark processed
        arc.processed = True
        session.add(arc)
        session.commit()
        logger.info(f"Unpacked {len(games)} games for {arc.month}")


# 3) Process all pending archives
def process_pending_archives():
    with Session(engine) as session:
        stmt = select(ArchiveMonth).where(ArchiveMonth.processed == False)
        pending = session.exec(stmt).all()
        for arc in pending:
            logger.info(f"Processing archive {arc.month}")
            unpack_archive(arc.id)
