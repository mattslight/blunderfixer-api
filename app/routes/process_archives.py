# === app/routes/process.py ===
from fastapi import APIRouter

from app.schemas import StatusResponse
from app.services import process_pending_archives

router = APIRouter()


@router.post("/process_archives", response_model=StatusResponse)
def process_archives():
    process_pending_archives()
    return StatusResponse(status="processing started")
