# app/routes/drills.py

from typing import List

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import selectinload
from sqlmodel import Session, select

from app.db import get_session
from app.models import DrillPosition, Game
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
        # join into Game so we can order by its played_at
        .join(DrillPosition.game)
        .options(selectinload(DrillPosition.game))
        .where(DrillPosition.username == username)
        .order_by(Game.played_at.desc())
        .limit(limit)
    )
    drills = session.exec(stmt).all()
    if not drills:
        # optional: 204 No Content or just return empty list
        return []
    # build a DRY list of Pydantic responses
    resp: List[DrillPositionResponse] = []
    for d in drills:
        g = d.game
        is_white = d.username == g.white_username

        hero_raw = g.white_result if is_white else g.black_result
        opp_raw = g.black_result if is_white else g.white_result
        draw = g.white_result == g.black_result

        if hero_raw == "win":
            hero_result, result_reason = "win", opp_raw
        elif draw:
            hero_result, result_reason = "draw", hero_raw
        else:
            hero_result, result_reason = "loss", hero_raw

        hero_rating = g.white_rating if is_white else g.black_rating
        opponent_username = g.black_username if is_white else g.white_username
        opponent_rating = g.black_rating if is_white else g.white_rating

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
                hero_rating=hero_rating,
                opponent_username=opponent_username,
                opponent_rating=opponent_rating,
                played_at=g.played_at,
            )
        )

    return resp
