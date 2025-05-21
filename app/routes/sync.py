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
    # use timezone-aware UTC now
    now = datetime.now(timezone.utc)
    current_month = now.strftime("%Y-%m")

    # load existing ArchiveMonth rows
    existing_rows = session.exec(
        select(ArchiveMonth).where(ArchiveMonth.username == req.username)
    ).all()
    existing = {arc.month: arc for arc in existing_rows}

    for month_str, raw in months:
        if month_str in existing:
            # only refresh the current month
            if month_str == current_month:
                arc = existing[month_str]
                arc.raw_json = raw
                arc.fetched_at = now
                arc.processed = False
                session.add(arc)
        else:
            # new month
            session.add(
                ArchiveMonth(
                    username=req.username,
                    month=month_str,
                    raw_json=raw,
                    fetched_at=now,
                )
            )

    session.commit()
    return SyncResponse(status="synced")
