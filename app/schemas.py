from pydantic import BaseModel
from typing import Dict

class AnalyzeRequest(BaseModel):
    fen: str
    top_n: int = 1

class GameSummary(BaseModel):
    total_games: int
    wins: int
    losses: int
    draws: int
    time_classes: Dict[str, int]
  
class ProfileResponse(BaseModel):
    username: str
    month: str
    summary: GameSummary