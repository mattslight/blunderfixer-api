# app/routes/player_stats/index.py

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import Integer, func
from sqlmodel import Session, select

from app.db import get_session
from app.models import Game
from app.routes.player_stats.schemas import (
    OverallStats,
    PlayerStatsResponse,
    TerminationStats,
    TimeClassStats,
    TimeControlStats,
)

router = APIRouter(prefix="/player_stats", tags=["player_stats"])


# --- Route handler ---
@router.get("/{username}", response_model=PlayerStatsResponse)
def get_player_stats(
    username: str,
    session: Session = Depends(get_session),
) -> PlayerStatsResponse:
    # Overall performance
    total, wins, losses, draws = session.exec(
        select(
            func.count().label("total"),
            func.sum((Game.result == "win").cast(Integer)).label("wins"),
            func.sum((Game.result == "loss").cast(Integer)).label("losses"),
            func.sum((Game.result == "draw").cast(Integer)).label("draws"),
        ).where(Game.username == username)
    ).one()

    if total == 0:
        raise HTTPException(status_code=404, detail="No games found for user")

    overall = OverallStats(
        total_games=total,
        wins=wins,
        losses=losses,
        draws=draws,
        win_rate_incl_draws=round(wins / total, 3),
        win_rate_excl_draws=round(
            wins / (wins + losses) if (wins + losses) > 0 else 0, 3
        ),
    )

    # By time_class
    rows_tc = session.exec(
        select(
            Game.time_class,
            func.count().label("games"),
            func.avg((Game.result == "win").cast(Integer)).label("win_rate"),
            func.avg((Game.result == "loss").cast(Integer)).label("loss_rate"),
            func.avg((Game.result == "draw").cast(Integer)).label("draw_rate"),
        )
        .where(Game.username == username)
        .group_by(Game.time_class)
    ).all()
    by_time_class = [TimeClassStats(**row._asdict()) for row in rows_tc]

    # By time_control
    rows_tctrl = session.exec(
        select(
            Game.time_control,
            func.count().label("games"),
            func.avg((Game.result == "win").cast(Integer)).label("win_rate"),
            func.avg((Game.result == "loss").cast(Integer)).label("loss_rate"),
            func.avg((Game.result == "draw").cast(Integer)).label("draw_rate"),
        )
        .where(Game.username == username)
        .group_by(Game.time_control)
    ).all()
    by_time_control = [TimeControlStats(**row._asdict()) for row in rows_tctrl]

    # By termination reason
    rows_term = session.exec(
        select(
            Game.termination,
            func.count().label("games"),
            func.avg((Game.result == "win").cast(Integer)).label("win_rate"),
            func.avg((Game.result == "loss").cast(Integer)).label("loss_rate"),
            func.avg((Game.result == "draw").cast(Integer)).label("draw_rate"),
        )
        .where(Game.username == username)
        .group_by(Game.termination)
    ).all()
    by_termination = [TerminationStats(**row._asdict()) for row in rows_term]

    return PlayerStatsResponse(
        overall=overall,
        by_time_class=by_time_class,
        by_time_control=by_time_control,
        by_termination=by_termination,
    )
