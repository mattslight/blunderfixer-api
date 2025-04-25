from fastapi import APIRouter
from datetime import datetime
from app.utils.fetch_games import fetch_games

router = APIRouter()
@router.get("/games/{username}",
            summary="Get Games",
            description="""
                        Fetches the user's games from Chess.com for the current month.

                        - Caches results to disk in `data/{username}/{YYYY-MM}.json`
                        - Returns the full game list as provided by Chess.com
                        """)
def get_games(username: str):
    now = datetime.utcnow()
    games = fetch_games(username, now.year, now.month)
    return {
        "username": username,
        "month": f"{now.year}-{now.month:02d}",
        "games_fetched": len(games),
        "games": games
    }