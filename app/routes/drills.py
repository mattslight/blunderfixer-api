from typing import List

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlmodel import Session, select

from app.db import get_session
from app.models import DrillPosition
from app.schemas import DrillPositionResponse

router = APIRouter(prefix="/drills", tags=["drills"])


@router.get("/", response_model=List[DrillPositionResponse])
def list_drills(
    username: str = Query(..., description="Hero username to fetch drills for"),
    limit: int = Query(50, ge=1, le=200),
    session: Session = Depends(get_session),
):
    stmt = (
        select(DrillPosition)
        .where(DrillPosition.username == username)
        .order_by(DrillPosition.created_at.desc())
        .limit(limit)
    )
    drills = session.exec(stmt).all()
    if not drills:
        # optional: 204 No Content or just return empty list
        return []
    return drills
