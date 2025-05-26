# app/routes/sync_all.py
from datetime import datetime, timezone

from fastapi import APIRouter, BackgroundTasks, Depends
from sqlmodel import Session, select

from app.db import get_session
from app.models import ActiveUser, Job
from app.schemas import SyncAllResponse
from app.services import run_sync_job

router = APIRouter()


@router.post("/sync_all", response_model=SyncAllResponse)
def sync_all_users(
    bg: BackgroundTasks,
    session: Session = Depends(get_session),
):
    # pull every active username
    usernames = session.exec(select(ActiveUser.username)).all()

    results: dict[str, str] = {}
    now = datetime.now(timezone.utc)

    for username in usernames:
        job = Job(
            username=username,
            action="sync_archives",
            status="queued",
            created_at=now,
            updated_at=now,
        )
        session.add(job)
        session.flush()  # populates job.id without full commit

        bg.add_task(run_sync_job, job.id)
        results[username] = job.id

    session.commit()
    return SyncAllResponse(results=results)
