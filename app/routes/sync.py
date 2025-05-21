# === app/routes/sync.py ===
from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from sqlmodel import Session, select

from app.db import get_session
from app.models import ArchiveMonth
from app.schemas import SyncRequest, SyncResponse
from app.services import fetch_archives

router = APIRouter()


@router.post("/sync", response_model=SyncResponse)
def sync_user(req: SyncRequest, session: Session = Depends(get_session)):
    months = fetch_archives(req.username)
    now = datetime.now(timezone.utc)
    current_month = now.strftime("%Y-%m")

    # pull down existing months
    existing = {
        arc.month: arc
        for arc in session.exec(
            select(ArchiveMonth).where(ArchiveMonth.username == req.username)
        )
    }

    buffer = []

    def flush():
        """commit and clear the buffer"""
        session.commit()
        buffer.clear()

    for month_str, raw in months:
        if month_str in existing:
            # only overwrite the current month
            if month_str != current_month:
                continue
            arc = existing[month_str]
            arc.raw_json = raw
            arc.fetched_at = now
            arc.processed = False
        else:
            arc = ArchiveMonth(
                username=req.username,
                month=month_str,
                raw_json=raw,
                fetched_at=now,
            )

        session.add(arc)
        buffer.append(arc)

        # once we have 5 pending, commit them
        if len(buffer) >= 5:
            flush()

    # commit any remainder
    if buffer:
        flush()

    return SyncResponse(status="synced")
