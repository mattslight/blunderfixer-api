from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict


class AnalyseRequest(BaseModel):
    fen: str
    top_n: int = 1


class LineInfo(BaseModel):
    rank: int  # the multipv rank, e.g. 1,2,3…
    moves: List[str]  # SAN moves, e.g. ["e4","e5","Nf3",…]
    scoreCP: Optional[int] = None  # centipawn score, if any
    mateIn: Optional[int] = None  # mate-in N, if any
    depth: int  # the depth you ran


class SyncRequest(BaseModel):
    username: str


class SyncAllResponse(BaseModel):
    results: dict[str, str]  # {username: job_id}


class SyncResponse(BaseModel):
    job_id: str


class SyncStatusResponse(BaseModel):
    job_id: str
    status: str
    total: int
    processed: int
    error: Optional[str]


class DrillHistoryCreate(BaseModel):
    result: str  # 'pass' | 'fail'
    reason: Optional[str] = None
    moves: Optional[list[str]] = None
    timestamp: Optional[datetime] = None  # optional, defaults to now if omitted


class DrillHistoryRead(BaseModel):
    id: int
    drill_position_id: int
    result: str
    reason: Optional[str]
    moves: list[str]
    final_eval: Optional[float] = None
    timestamp: datetime

    model_config = ConfigDict(from_attributes=True)


class GameResponse(BaseModel):
    """Subset of Game fields returned with a drill."""

    id: str
    game_uuid: str
    url: str
    played_at: datetime
    end_time: datetime
    time_class: str
    time_control: str
    white_username: str
    white_rating: int
    white_result: str
    black_username: str
    black_rating: int
    black_result: str
    eco: str
    eco_url: Optional[str] = None
    pgn: str

    model_config = ConfigDict(from_attributes=True)


class DrillPositionResponse(BaseModel):
    id: int
    game_id: str
    username: str
    fen: str
    ply: int
    initial_eval: float
    eval_swing: float
    created_at: datetime
    hero_result: str
    result_reason: str
    time_control: str
    time_class: str
    hero_rating: int
    opponent_username: str
    opponent_rating: int
    game_played_at: datetime
    phase: str
    archived: bool
    has_one_winning_move: bool = False
    winning_moves: Optional[list[str]] = None
    winning_lines: Optional[list[list[str]]] = None
    losing_move: Optional[str] = None
    features: Optional[Dict[str, Any]] = None
    mastered: bool
    history: list[DrillHistoryRead] = []
    last_drilled_at: Optional[datetime] = None
    game: Optional[GameResponse] = None
    model_config = ConfigDict(from_attributes=True)


class DrillUpdateRequest(BaseModel):
    """Fields that can be updated on a drill."""

    archived: Optional[bool] = None
    mark_played: Optional[bool] = None
