from datetime import datetime
from typing import List, Optional

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
    timestamp: Optional[datetime] = None  # optional, defaults to now if omitted


class DrillHistoryRead(BaseModel):
    id: int
    drill_position_id: int
    result: str
    reason: Optional[str]
    timestamp: datetime

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
    played_at: datetime
    phase: str
    history: list[DrillHistoryRead] = []

    model_config = ConfigDict(from_attributes=True)
