"""/drills endpoint  –  self‑contained, readable version

Key ideas
──────────
•  Pure‑SQL filters for username, eval‑swing, opponent substring ➜ fast.
•  Phase/result filters need derived info ➜ done in Python, *then* capped to `limit`.
•  Progressive batching (batch = limit×4) avoids loading the whole table when it’s big.
•  All external inputs normalised/cast early so the rest of the code is type‑safe.

All variable names aim to be self‑explanatory; short in‑line comments explain every non‑obvious step.
"""

import sys
from datetime import datetime, timezone
from math import ceil
from typing import List, Optional

from fastapi import APIRouter, Body, Depends, HTTPException, Path, Query
from sqlalchemy import or_
from sqlalchemy.orm import selectinload
from sqlmodel import Session, select

from app.db import get_session
from app.models import DrillHistory, DrillPosition, Game
from app.schemas import DrillHistoryCreate, DrillHistoryRead, DrillPositionResponse

router = APIRouter(prefix="/drills", tags=["drills"])

# ---------------------------------------------------------------------------
# Helper: phase classifier
# ---------------------------------------------------------------------------


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
    """Return one of  opening | middle | late | endgame  for a given position."""

    move_no = ceil(ply / 2)

    # If any material fields are missing we fall back to a coarse heuristic
    if None in (
        has_white_queen,
        has_black_queen,
        white_rook_count,
        black_rook_count,
        white_minor_count,
        black_minor_count,
    ):
        return "opening" if move_no < opening_move_threshold else "middle"

    # Opening: before threshold and ≥1 queen still on board
    if move_no < opening_move_threshold and (has_white_queen or has_black_queen):
        return "opening"

    # Otherwise evaluate material balance on the richer side
    white_pts = int(has_white_queen) * 2 + white_rook_count + white_minor_count
    black_pts = int(has_black_queen) * 2 + black_rook_count + black_minor_count
    material = max(white_pts, black_pts)

    if material >= 5:
        return "middle"
    if material >= 3:  # 3–4 points
        return "late"
    return "endgame"


# ---------------------------------------------------------------------------
# Main route
# ---------------------------------------------------------------------------


@router.get("/", response_model=List[DrillPositionResponse])
def list_drills(
    username: str = Query(..., description="Hero username"),
    limit: int = Query(100, ge=1, le=200, description="Max rows to return"),
    opening_threshold: int = Query(
        10, ge=1, description="Full‑move boundary for opening"
    ),
    # Swing bounds – floats accepted for convenience, cast to int (centipawns) for SQL
    min_eval_swing: float = Query(0, ge=0),
    max_eval_swing: float = Query(float("inf"), ge=0),
    phases: Optional[List[str]] = Query(
        None, description="opening|middle|late|endgame"
    ),
    hero_results: Optional[List[str]] = Query(None, description="win|loss|draw"),
    opponent: Optional[str] = Query(
        None, description="Substring match (ILIKE) for opponent username"
    ),
    include: Optional[List[str]] = Query(
        None,
        description="Include hidden drills: 'archived' and/or 'mastered'",
    ),
    session: Session = Depends(get_session),
) -> List[DrillPositionResponse]:

    # --- Normalise external inputs -----------------------------------------
    min_eval_cp = int(min_eval_swing)
    max_eval_cp = sys.maxsize if max_eval_swing == float("inf") else int(max_eval_swing)

    phase_whitelist = {p.lower() for p in phases or []}
    result_whitelist = {r.lower() for r in hero_results or []}

    include_set = {item.lower() for item in include or []}
    include_archived = "archived" in include_set
    include_mastered = "mastered" in include_set

    # Batch size for progressive fetch: 4× requested limit is a good trade‑off
    batch_size = limit * 4
    offset = 0
    results: List[DrillPositionResponse] = []

    while len(results) < limit:
        # ----------------- SQL build (cheap filters only) -------------------
        filters = [
            DrillPosition.username == username,
            DrillPosition.eval_swing >= min_eval_cp,
            DrillPosition.eval_swing <= max_eval_cp,
        ]
        if not include_archived:
            filters.append(DrillPosition.archived == False)

        query = (
            select(DrillPosition)
            .join(DrillPosition.game)
            .options(
                selectinload(DrillPosition.game),
                selectinload(DrillPosition.history),
            )
            .where(*filters)
            .order_by(Game.played_at.desc(), DrillPosition.created_at.desc())
            .offset(offset)
            .limit(batch_size)
        )

        if opponent:
            opponent_like = f"%{opponent}%"
            query = query.where(
                or_(
                    Game.white_username.ilike(opponent_like),
                    Game.black_username.ilike(opponent_like),
                )
            )

        rows = session.exec(query).all()
        if not rows:  # ran out of data
            break

        # ----------------- Python‑level filters ----------------------------
        for dp in rows:
            game = dp.game
            hero_is_white = dp.username == game.white_username

            if not include_mastered:
                # Skip drills with 5 most recent passes (mastered)
                history_sorted = sorted(dp.history, key=lambda h: h.timestamp, reverse=True)
                recent = history_sorted[:5]
                if len(recent) == 5 and all(h.result == "pass" for h in recent):
                    continue

            hero_raw = game.white_result if hero_is_white else game.black_result
            opp_raw = game.black_result if hero_is_white else game.white_result
            is_draw = game.white_result == game.black_result
            hero_res = "win" if hero_raw == "win" else "draw" if is_draw else "loss"

            if result_whitelist and hero_res not in result_whitelist:
                continue

            phase = classify_phase(
                dp.ply,
                dp.white_queen,
                dp.black_queen,
                dp.white_rook_count,
                dp.black_rook_count,
                dp.white_minor_count,
                dp.black_minor_count,
                opening_threshold,
            )
            if phase_whitelist and phase not in phase_whitelist:
                continue

            results.append(
                DrillPositionResponse(
                    id=dp.id,
                    game_id=dp.game_id,
                    username=dp.username,
                    fen=dp.fen,
                    ply=dp.ply,
                    initial_eval=dp.initial_eval,
                    eval_swing=dp.eval_swing,
                    created_at=dp.created_at,
                    hero_result=hero_res,
                    result_reason=opp_raw if hero_res == "win" else hero_raw,
                    time_control=game.time_control,
                    time_class=game.time_class,
                    hero_rating=(
                        game.white_rating if hero_is_white else game.black_rating
                    ),
                    opponent_username=(
                        game.black_username if hero_is_white else game.white_username
                    ),
                    opponent_rating=(
                        game.black_rating if hero_is_white else game.white_rating
                    ),
                    played_at=game.played_at,
                    phase=phase,
                    archived=dp.archived,
                    history=[DrillHistoryRead.from_orm(h) for h in dp.history],
                )
            )
            if len(results) == limit:
                break

        offset += batch_size  # next SQL window

    return results[:limit]  # safety slice (rarely needed)


@router.get("/{id}", response_model=DrillPositionResponse)
def get_drill(
    id: int,
    session: Session = Depends(get_session),
) -> DrillPositionResponse:
    stmt = (
        select(DrillPosition)
        .where(DrillPosition.id == id)
        .options(
            selectinload(DrillPosition.game),
            selectinload(DrillPosition.history),  # ? eagerly load history
        )
    )
    drill: DrillPosition = session.exec(stmt).one_or_none()
    if not drill:
        raise HTTPException(status_code=404, detail="Drill not found")

    game = drill.game
    hero_is_white = drill.username == game.white_username

    hero_raw = game.white_result if hero_is_white else game.black_result
    opp_raw = game.black_result if hero_is_white else game.white_result
    is_draw = game.white_result == game.black_result
    hero_res = "win" if hero_raw == "win" else "draw" if is_draw else "loss"

    phase = classify_phase(
        drill.ply,
        drill.white_queen,
        drill.black_queen,
        drill.white_rook_count,
        drill.black_rook_count,
        drill.white_minor_count,
        drill.black_minor_count,
    )

    return DrillPositionResponse(
        id=drill.id,
        game_id=drill.game_id,
        username=drill.username,
        fen=drill.fen,
        ply=drill.ply,
        initial_eval=drill.initial_eval,
        eval_swing=drill.eval_swing,
        created_at=drill.created_at,
        hero_result=hero_res,
        result_reason=opp_raw if hero_res == "win" else hero_raw,
        time_control=game.time_control,
        time_class=game.time_class,
        hero_rating=game.white_rating if hero_is_white else game.black_rating,
        opponent_username=game.black_username if hero_is_white else game.white_username,
        opponent_rating=game.black_rating if hero_is_white else game.white_rating,
        played_at=game.played_at,
        phase=phase,
        archived=drill.archived,
        history=[DrillHistoryRead.from_orm(h) for h in drill.history],
    )


@router.get("/{drill_id}/history", response_model=list[DrillHistoryRead])
def read_drill_history(
    *,
    drill_id: int = Path(..., description="ID of the drill position"),
    session: Session = Depends(get_session),
):
    """
    Fetch all history entries for a given drill_position_id,
    ordered by timestamp descending.
    """
    statement = (
        select(DrillHistory)
        .where(DrillHistory.drill_position_id == drill_id)
        .order_by(DrillHistory.timestamp.desc())
    )
    history_rows = session.exec(statement).all()
    return history_rows


@router.post(
    "/{drill_id}/history",
    response_model=DrillHistoryRead,
    status_code=201,
)
def create_drill_history(
    *,
    drill_id: int = Path(..., description="ID of the drill position"),
    payload: DrillHistoryCreate = Body(
        ..., description="Result payload: 'pass' | 'fail', optional timestamp"
    ),
    session: Session = Depends(get_session),
):
    """
    Record a new history entry for drill_position_id == drill_id.
    - `payload.result` must be 'pass' or 'fail'.
    - `payload.timestamp` defaults to now if omitted.
    """
    # (Optional) Verify that the DrillPosition exists:
    from app.models import DrillPosition

    # Check payload
    result_lower = payload.result.lower()
    if result_lower not in {"pass", "fail"}:
        raise HTTPException(status_code=400, detail="Invalid result")

    dp = session.get(DrillPosition, drill_id)
    if not dp:
        raise HTTPException(status_code=404, detail="DrillPosition not found")

    # Create & insert
    ts = payload.timestamp or datetime.now(timezone.utc)
    new_hist = DrillHistory(
        drill_position_id=drill_id,
        result=result_lower,
        reason=payload.reason,
        timestamp=ts,
    )
    session.add(new_hist)
    session.commit()
    session.refresh(new_hist)
    return new_hist
