from math import ceil
from typing import List, Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import selectinload
from sqlmodel import Session, select

from app.db import get_session
from app.models import DrillPosition, Game
from app.schemas import DrillPositionResponse

router = APIRouter(prefix="/drills", tags=["drills"])


def classify_phase(
    ply: int,
    has_white_queen: Optional[bool],
    has_black_queen: Optional[bool],
    white_rook_count: Optional[int],
    black_rook_count: Optional[int],
    white_minor_count: Optional[int],
    black_minor_count: Optional[int],
    opening_move_threshold: int = 10,
) -> str:
    """
    Return one of: 'opening', 'middle', 'late', 'endgame'.

    Rules (v2):
    • Opening  – move < 10  AND at least one queen on board
    • Otherwise:
        material = queens*2 + rooks + minors   (both sides)
        ≥5  → middle
        3–4 → late
        ≤2 → endgame
    """
    move_number = ceil(ply / 2)

    # Fallback when data is missing
    if None in (
        has_white_queen,
        has_black_queen,
        white_rook_count,
        black_rook_count,
        white_minor_count,
        black_minor_count,
    ):
        return "opening" if move_number < opening_move_threshold else "middle"

    total_queens = int(has_white_queen) + int(has_black_queen)
    if move_number < opening_move_threshold and total_queens:
        return "opening"

    # per-side, take the larger side’s score
    white_pts = int(has_white_queen) * 2 + white_rook_count + white_minor_count
    black_pts = int(has_black_queen) * 2 + black_rook_count + black_minor_count
    material_pts = max(white_pts, black_pts)

    if material_pts >= 5:
        return "middle"
    if material_pts >= 3:  # 3-4
        return "late"
    return "endgame"


@router.get("/", response_model=List[DrillPositionResponse])
def list_drills(
    username: str = Query(..., description="Hero username to fetch drills for"),
    limit: int = Query(100, ge=1, le=200),
    opening_threshold: int = Query(
        10, ge=1, description="Max full-move number for 'opening' phase"
    ),
    session: Session = Depends(get_session),
) -> List[DrillPositionResponse]:
    stmt = (
        select(DrillPosition)
        .join(DrillPosition.game)
        .options(selectinload(DrillPosition.game))
        .where(DrillPosition.username == username)
        .order_by(
            Game.played_at.desc(),
            DrillPosition.created_at.desc(),
        )
        .limit(limit)
    )
    drills = session.exec(stmt).all()
    if not drills:
        return []

    resp: List[DrillPositionResponse] = []
    for d in drills:
        g = d.game
        is_white = d.username == g.white_username

        # derive result
        hero_raw = g.white_result if is_white else g.black_result
        opp_raw = g.black_result if is_white else g.white_result
        draw = g.white_result == g.black_result
        if hero_raw == "win":
            hero_result, result_reason = "win", opp_raw
        elif draw:
            hero_result, result_reason = "draw", hero_raw
        else:
            hero_result, result_reason = "loss", hero_raw

        # classify phase
        phase = classify_phase(
            d.ply,
            d.white_queen,
            d.black_queen,
            d.white_rook_count,
            d.black_rook_count,
            d.white_minor_count,
            d.black_minor_count,
            opening_threshold,
        )

        resp.append(
            DrillPositionResponse(
                id=d.id,
                game_id=d.game_id,
                username=d.username,
                fen=d.fen,
                ply=d.ply,
                eval_swing=d.eval_swing,
                created_at=d.created_at,
                hero_result=hero_result,
                result_reason=result_reason,
                time_control=g.time_control,
                time_class=g.time_class,
                hero_rating=g.white_rating if is_white else g.black_rating,
                opponent_username=g.black_username if is_white else g.white_username,
                opponent_rating=g.black_rating if is_white else g.white_rating,
                played_at=g.played_at,
                phase=phase,
            )
        )

    return resp
