from fastapi import APIRouter
from datetime import datetime
from app.utils import get_games, summarize_games
from app.schemas import ProfileResponse

router = APIRouter()

@router.get("/profile/{username}", response_model=ProfileResponse)
def get_profile_summary(username: str):
    now = datetime.utcnow()
    games = get_games(username, now.year, now.month)
    summary = summarize_games(games)

    return {
        "username": username,
        "month": f"{now.year}-{now.month:02d}",
        "summary": summary
    }
