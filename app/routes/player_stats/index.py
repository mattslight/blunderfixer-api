# app/routes/player_stats/index.py

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import Integer, case, func
from sqlmodel import Session, select

from app.db import get_session
from app.models import DrillHistory, DrillPosition, Game
from app.routes.player_stats.schemas import (
    EcoFamilyStats,
    EcoStats,
    EloProgressionEntry,
    EloSeries,
    OpponentStats,
    OverallStats,
    BlundersFixedResponse,
    PlayerStatsResponse,
    RatingBucketStats,
    TerminationStats,
    TimeClassStats,
    TimeControlStats,
)

router = APIRouter(prefix="/player_stats", tags=["player_stats"])


@router.get("/{username}", response_model=PlayerStatsResponse)
def get_player_stats(
    username: str,
    session: Session = Depends(get_session),
) -> PlayerStatsResponse:
    # Base filter: games where user is white or black
    white_cond = Game.white_username == username
    black_cond = Game.black_username == username
    user_filter = white_cond | black_cond

    # Define win/loss/draw cases
    win_case = case(
        (white_cond & (Game.white_result == "win"), 1),
        (black_cond & (Game.black_result == "win"), 1),
        else_=0,
    )
    loss_case = case(
        (white_cond & (Game.white_result == "loss"), 1),
        (black_cond & (Game.black_result == "loss"), 1),
        else_=0,
    )
    draw_case = case(
        (white_cond & (Game.white_result == "draw"), 1),
        (black_cond & (Game.black_result == "draw"), 1),
        else_=0,
    )

    # 1. Overall performance
    total, wins, losses, draws = session.exec(
        select(
            func.count().label("total"),
            func.sum(win_case).cast(Integer).label("wins"),
            func.sum(loss_case).cast(Integer).label("losses"),
            func.sum(draw_case).cast(Integer).label("draws"),
        ).where(user_filter)
    ).one()
    if total == 0:
        raise HTTPException(404, "No games found for user")

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

    # 2A. Breakdown by time_class
    rows_tc = session.exec(
        select(
            Game.time_class.label("time_class"),
            func.count().label("games"),
            (func.sum(win_case) / func.count()).label("win_rate"),
            (func.sum(loss_case) / func.count()).label("loss_rate"),
            (func.sum(draw_case) / func.count()).label("draw_rate"),
        )
        .where(user_filter)
        .group_by(Game.time_class)
    ).all()
    by_time_class = [TimeClassStats(**r._asdict()) for r in rows_tc]

    # 2B. Breakdown by time_control
    rows_tctrl = session.exec(
        select(
            Game.time_control.label("time_control"),
            func.count().label("games"),
            (func.sum(win_case) / func.count()).label("win_rate"),
            (func.sum(loss_case) / func.count()).label("loss_rate"),
            (func.sum(draw_case) / func.count()).label("draw_rate"),
        )
        .where(user_filter)
        .group_by(Game.time_control)
    ).all()
    by_time_control = [TimeControlStats(**r._asdict()) for r in rows_tctrl]

    # 5. Breakdown by result (raw)
    result_expr = case(
        (white_cond, Game.white_result),
        (black_cond, Game.black_result),
        else_="unknown",
    ).label("result")
    rows_res = session.exec(
        select(
            result_expr,
            func.count().label("games"),
            (func.sum(win_case) / func.count()).label("win_rate"),
            (func.sum(loss_case) / func.count()).label("loss_rate"),
            (func.sum(draw_case) / func.count()).label("draw_rate"),
        )
        .where(user_filter)
        .group_by(result_expr)
    ).all()
    by_termination = [TerminationStats(**r._asdict()) for r in rows_res]

    # 4A. Openings by ECO code
    rows_eco = session.exec(
        select(
            Game.eco.label("eco"),
            func.count().label("games"),
            (func.sum(win_case) / func.count()).label("win_rate"),
            (func.sum(loss_case) / func.count()).label("loss_rate"),
            (func.sum(draw_case) / func.count()).label("draw_rate"),
        )
        .where(user_filter)
        .group_by(Game.eco)
    ).all()
    by_eco = [EcoStats(**r._asdict()) for r in rows_eco]

    # 4B. Openings by ECO family (first letter)
    eco_family = func.substr(Game.eco, 1, 1).label("family")
    rows_family = session.exec(
        select(
            eco_family,
            func.count().label("games"),
            (func.sum(win_case) / func.count()).label("win_rate"),
        )
        .where(user_filter)
        .group_by(eco_family)
    ).all()
    by_eco_family = [
        EcoFamilyStats(family=r.family, games=r.games, win_rate=r.win_rate)
        for r in rows_family
    ]

    # 7A. Average opponent rating by result
    opp_rating_expr = case(
        (white_cond, Game.black_rating),
        (black_cond, Game.white_rating),
    ).label("opp_rating")
    rows_opp_rating = session.exec(
        select(
            result_expr,
            func.avg(opp_rating_expr).label("avg_opp_rating"),
        )
        .where(user_filter)
        .group_by(result_expr)
    ).all()
    avg_opp_rating = [
        OpponentStats(result=r.result, avg_rating=r.avg_opp_rating)
        for r in rows_opp_rating
    ]

    # 7B. Rating difference buckets
    diff = (
        case(
            (white_cond, Game.black_rating - Game.white_rating),
            (black_cond, Game.white_rating - Game.black_rating),
        )
    ).label("diff")
    bucket = (
        case(
            (diff <= -200, "<=-200"),
            (diff <= -100, "-200..-101"),
            (diff < 0, "-100..-1"),
            (diff < 100, "0..99"),
            (diff < 200, "100..199"),
            else_=">=200",
        )
    ).label("bucket")
    rows_bucket = session.exec(
        select(
            bucket,
            func.count().label("games"),
            (func.sum(win_case) / func.count()).label("win_rate"),
        )
        .where(user_filter)
        .group_by(bucket)
    ).all()
    rating_buckets = [RatingBucketStats(**r._asdict()) for r in rows_bucket]

    # 7C. Most-faced opponents
    opp_user = case(
        (white_cond, Game.black_username), (black_cond, Game.white_username)
    ).label("opp_user")
    rows_opponents = session.exec(
        select(
            opp_user,
            func.count().label("games"),
            func.sum(win_case).label("wins"),
            func.sum(loss_case).label("losses"),
            func.sum(draw_case).label("draws"),
        )
        .where(user_filter)
        .group_by(opp_user)
        .order_by(func.count().desc())
        .limit(10)
    ).all()
    most_faced = [
        OpponentStats(
            username=r.opp_user,
            games=r.games,
            wins=r.wins,
            losses=r.losses,
            draws=r.draws,
        )
        for r in rows_opponents
    ]

    # 7D. Elo progression
    rows_elo = session.exec(
        select(
            Game.time_class.label("time_class"),  # NEW
            case(
                (white_cond, Game.played_at),
                (black_cond, Game.played_at),
            ).label("played_at"),
            case(
                (white_cond, Game.white_rating),
                (black_cond, Game.black_rating),
            ).label("rating"),
        )
        .where(user_filter)
        .order_by(Game.time_class, "played_at")  # keep each series sorted
    ).all()

    series_map: dict[str, list[EloProgressionEntry]] = {}

    for r in rows_elo:
        series_map.setdefault(r.time_class, []).append(
            EloProgressionEntry(played_at=r.played_at, rating=r.rating)
        )

    elo_progression = [
        EloSeries(time_class=tc, entries=entries)  # <-- your new schema
        for tc, entries in series_map.items()
    ]

    return PlayerStatsResponse(
        overall=overall,
        by_time_class=by_time_class,
        by_time_control=by_time_control,
        by_termination=by_termination,
        by_eco=by_eco,
        by_eco_family=by_eco_family,
        avg_opp_rating=avg_opp_rating,
        rating_buckets=rating_buckets,
        most_faced=most_faced,
        elo_progression=elo_progression,
    )


@router.get("/{username}/blunders_fixed", response_model=BlundersFixedResponse)
def get_blunders_fixed(
    username: str,
    session: Session = Depends(get_session),
) -> BlundersFixedResponse:
    count = session.exec(
        select(func.count())
        .select_from(DrillHistory)
        .join(DrillPosition, DrillHistory.drill_position_id == DrillPosition.id)
        .where(DrillPosition.username == username)
        .where(DrillHistory.result == "pass")
    ).one()[0]

    return BlundersFixedResponse(username=username, blunders_fixed=count)
