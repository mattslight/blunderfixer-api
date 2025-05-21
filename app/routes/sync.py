from datetime import datetime, timezone

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlmodel import Session, select

from app.db import get_session
from app.models import ArchiveMonth, Job
from app.schemas import SyncRequest, SyncResponse, SyncStatusResponse
from app.services import fetch_archives, run_sync_job  # we’ll write run_sync_job next

router = APIRouter()


@router.post("/sync", response_model=SyncResponse)
def sync_user(
    req: SyncRequest,
    bg: BackgroundTasks,
    session: Session = Depends(get_session),
):
    # 1) create the job record
    job = Job(
        username=req.username,
        action="sync_archives",
        status="queued",
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    session.add(job)
    session.commit()  # now job.id is populated

    # 2) enqueue background work, passing job.id
    bg.add_task(run_sync_job, job.id)

    # 3) immediately return the job id
    return SyncResponse(job_id=job.id)


@router.get("/sync/{job_id}", response_model=SyncStatusResponse)
def sync_status(job_id: str, session: Session = Depends(get_session)):
    job = session.get(Job, job_id)
    if not job:
        raise HTTPException(404, "Job not found")
    return SyncStatusResponse(
        job_id=job.id,
        status=job.status,
        total=job.total,
        processed=job.processed,
        error=job.error,
    )
