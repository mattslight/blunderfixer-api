from datetime import datetime
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
    result: Optional[str]
    games: int
    win_rate: float
    loss_rate: float
    draw_rate: float


class EcoStats(BaseModel):
    eco: str
    games: int
    win_rate: float
    loss_rate: float
    draw_rate: float


class EcoFamilyStats(BaseModel):
    family: str
    games: int
    win_rate: float


class OpponentStats(BaseModel):
    # used for avg opponent rating by result or most-faced opponents
    result: Optional[str] = None
    avg_rating: Optional[float] = None
    username: Optional[str] = None
    games: Optional[int] = None
    wins: Optional[int] = None
    losses: Optional[int] = None
    draws: Optional[int] = None


class RatingBucketStats(BaseModel):
    bucket: str
    games: int
    win_rate: float


class EloProgressionEntry(BaseModel):
    played_at: datetime
    rating: int


class EloSeries(BaseModel):
    time_class: str  # bullet / blitz / rapid / daily
    entries: list[EloProgressionEntry]


class PlayerStatsResponse(BaseModel):
    overall: OverallStats
    by_time_class: List[TimeClassStats] = []
    by_time_control: List[TimeControlStats] = []
    by_termination: List[TerminationStats] = []
    by_eco: List[EcoStats] = []
    by_eco_family: List[EcoFamilyStats] = []
    avg_opp_rating: List[OpponentStats] = []
    rating_buckets: List[RatingBucketStats] = []
    most_faced: List[OpponentStats] = []
    elo_progression: List[EloSeries] = []


class BlundersFixedResponse(BaseModel):
    """Total number of drills a user has passed at least once."""

    username: str
    blunders_fixed: int
