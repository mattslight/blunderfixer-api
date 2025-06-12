from typing import List, Optional

from fastapi import APIRouter, Body, Depends, HTTPException, Path, Query
from sqlmodel import Session

from app.db import get_session
from app.schemas import (
    DrillHistoryCreate,
    DrillHistoryRead,
    DrillPositionResponse,
    DrillUpdateRequest,
)
from app.services.drills_service import DrillService, DrillNotFound, InvalidResult

router = APIRouter(prefix="/drills", tags=["drills"])


@router.get("/", response_model=List[DrillPositionResponse])
def list_drills(
    username: str = Query(..., description="Hero username"),
    limit: int = Query(100, ge=1, le=200, description="Max rows to return"),
    opening_threshold: int = Query(10, ge=1, description="Full-move boundary for opening"),
    min_eval_swing: float = Query(0, ge=0),
    max_eval_swing: float = Query(float("inf"), ge=0),
    phases: Optional[List[str]] = Query(None, description="opening|middle|late|endgame"),
    hero_results: Optional[List[str]] = Query(None, description="win|loss|draw"),
    opponent: Optional[str] = Query(None, description="Substring match (ILIKE) for opponent username"),
    include: Optional[List[str]] = Query(None, description="Include hidden drills: 'archived' and/or 'mastered'"),
    recent_first: bool = Query(False, description="Sort by most recently drilled first"),
    session: Session = Depends(get_session),
) -> List[DrillPositionResponse]:
    service = DrillService(session)
    return service.list_drills(
        username=username,
        limit=limit,
        opening_threshold=opening_threshold,
        min_eval_swing=min_eval_swing,
        max_eval_swing=max_eval_swing,
        phases=phases,
        hero_results=hero_results,
        opponent=opponent,
        include=include,
        recent_first=recent_first,
    )


@router.get("/recent", response_model=List[DrillPositionResponse])
def recent_drills(
    username: str = Query(..., description="Hero username"),
    limit: int = Query(20, ge=1, le=200, description="Max rows to return"),
    include_archived: bool = Query(False, description="Include archived drills"),
    session: Session = Depends(get_session),
) -> List[DrillPositionResponse]:
    service = DrillService(session)
    return service.recent_drills(
        username=username,
        limit=limit,
        include_archived=include_archived,
    )


@router.get("/mastered", response_model=List[DrillPositionResponse])
def mastered_drills(
    username: str = Query(..., description="Hero username"),
    limit: int = Query(20, ge=1, le=200, description="Max rows to return"),
    include_archived: bool = Query(False, description="Include archived drills"),
    session: Session = Depends(get_session),
) -> List[DrillPositionResponse]:
    service = DrillService(session)
    return service.mastered_drills(
        username=username,
        limit=limit,
        include_archived=include_archived,
    )


@router.get("/{id}", response_model=DrillPositionResponse)
def get_drill(
    id: int,
    session: Session = Depends(get_session),
) -> DrillPositionResponse:
    service = DrillService(session)
    try:
        return service.get_drill(drill_id=id)
    except DrillNotFound:
        raise HTTPException(status_code=404, detail="Drill not found")


@router.get("/{drill_id}/history", response_model=list[DrillHistoryRead])
def read_drill_history(
    *,
    drill_id: int = Path(..., description="ID of the drill position"),
    session: Session = Depends(get_session),
):
    service = DrillService(session)
    return service.read_drill_history(drill_id=drill_id)


@router.post(
    "/{drill_id}/history",
    response_model=DrillHistoryRead,
    status_code=201,
)
def create_drill_history(
    *,
    drill_id: int = Path(..., description="ID of the drill position"),
    payload: DrillHistoryCreate = Body(..., description="Result payload: 'pass' | 'fail', optional timestamp and moves; final eval computed automatically"),
    session: Session = Depends(get_session),
):
    service = DrillService(session)
    try:
        return service.create_drill_history(drill_id=drill_id, payload=payload)
    except DrillNotFound:
        raise HTTPException(status_code=404, detail="DrillPosition not found")
    except InvalidResult:
        raise HTTPException(status_code=400, detail="Invalid result")


@router.patch(
    "/{drill_id}",
    response_model=DrillPositionResponse,
    status_code=200,
)
def update_drill(
    *,
    drill_id: int = Path(..., description="ID of the drill position"),
    payload: DrillUpdateRequest = Body(..., description="Fields to update"),
    session: Session = Depends(get_session),
):
    service = DrillService(session)
    try:
        return service.update_drill(drill_id=drill_id, payload=payload)
    except DrillNotFound:
        raise HTTPException(status_code=404, detail="DrillPosition not found")

