from fastapi import APIRouter
from app.utils import get_games, summarize_games
from datetime import datetime


router = APIRouter()

@router.get("/openings/{username}")
def get_full_openings(username: str):
    now = datetime.utcnow()
    games = get_games(username, now.year, now.month)
    _, openings = summarize_games(games, username)
    return openings