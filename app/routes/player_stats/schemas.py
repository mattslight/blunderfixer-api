# app/routes/player_stats/schemas.py

from typing import List, Optional

from pydantic import BaseModel


# --- Local response schemas ---
class OverallStats(BaseModel):
    total_games: int
    wins: int
    losses: int
    draws: int
    win_rate_incl_draws: float  # wins / total
    win_rate_excl_draws: float  # wins / (wins+losses)


class TimeClassStats(BaseModel):
    time_class: str
    games: int
    win_rate: float
    loss_rate: float
    draw_rate: float


class TimeControlStats(BaseModel):
    time_control: str
    games: int
    win_rate: float
    loss_rate: float
    draw_rate: float


class TerminationStats(BaseModel):
    termination: Optional[str]
    games: int
    win_rate: float
    loss_rate: float
    draw_rate: float


class PlayerStatsResponse(BaseModel):
    overall: OverallStats
    by_time_class: List[TimeClassStats]
    by_time_control: List[TimeControlStats]
    by_termination: List[TerminationStats]
