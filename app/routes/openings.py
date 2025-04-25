from fastapi import APIRouter
from app.utils.summarise_games import summarise_games
from app.utils.fetch_games import fetch_games
from datetime import datetime


router = APIRouter()

@router.get("/openings/{username}",
            description="""
                        Returns performance statistics for all openings played by the user in the current month.

                        Includes:
                        - Total games per opening (min 1)
                        - Win/loss/draw counts and win rate
                        - Hero color (white or black)
                        - ECO codes and URLs (from PGN headers)
                        """)

def get_full_openings(username: str):
    now = datetime.utcnow()
    games = fetch_games(username, now.year, now.month)
    _, openings = summarise_games(games, username)
    return openings