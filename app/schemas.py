from typing import Any, Dict, List, Optional, Union

from pydantic import BaseModel


class AnalyseRequest(BaseModel):
    fen: str
    top_n: int = 1


class GameSummary(BaseModel):
    total_games: int
    wins: int
    losses: int
    draws: int
    time_classes: Dict[str, int]
    avg_moves: float
    training_suggestion: str
    most_common_opening: str
    openings: Dict[
        str, List[Dict[str, Union[str, float, int]]]
    ]  # Adjusted for correct types
    win_types: Dict[
        str, int
    ]  # Added for tracking win types (e.g., checkmate, timeout, etc.)
    loss_types: Dict[
        str, int
    ]  # Added for tracking loss types (e.g., checkmated, resigned, etc.)


class ProfileResponse(BaseModel):
    username: str
    month: str
    summary: GameSummary


class MoveInfo(BaseModel):
    move: str
    evaluation: float
    line: List[str]


class LineInfo(BaseModel):
    rank: int  # the multipv rank, e.g. 1,2,3…
    moves: List[str]  # SAN moves, e.g. ["e4","e5","Nf3",…]
    scoreCP: Optional[int] = None  # centipawn score, if any
    mateIn: Optional[int] = None  # mate-in N, if any
    searchDepth: int  # the depth you ran


class ExplanationRequest(BaseModel):
    fen: str
    lines: List[LineInfo]  # renamed from top_moves
    legal_moves: List[str]
    features: Dict[str, Any]
