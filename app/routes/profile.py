from fastapi import APIRouter
from datetime import datetime
from app.utils.summarise_games import summarise_games
from app.utils.fetch_games import fetch_games
from app.schemas import ProfileResponse

router = APIRouter()

@router.get("/profile/{username}", response_model=ProfileResponse, summary="Get Profile Summary",
            description="""
                        Returns a summary of the user's performance for the current month.

                        Includes:
                        - Total wins, losses, draws
                        - Average moves
                        - Time class breakdown
                        - Best and worst openings (min 5 games per opening)
                        """
)
def get_profile_summary(username: str):
    now = datetime.utcnow()
    games = fetch_games(username, now.year, now.month)
    summary, openings = summarise_games(games, username)

    # Filter top and bottom 5 (games >= 5)
    filtered = {k: v for k, v in openings.items() if v["games"] >= 5}
    sorted_openings = sorted(filtered.items(), key=lambda x: x[1]["win_rate"], reverse=True)


    summary["openings"] = {
        "best": [
            {
                "name": k, 
                "win_rate": v["win_rate"], 
                "games": v["games"], 
                "hero_color": v["hero_color"],  # Ensure hero_color is included
                "eco": v["eco"],
                "eco_url": v["eco_url"]
            }
            for k, v in sorted_openings[:5]
        ],
        "worst": [
            {
                "name": k, 
                "win_rate": v["win_rate"], 
                "games": v["games"], 
                "hero_color": v["hero_color"],  # Ensure hero_color is included
                "eco": v["eco"],
                "eco_url": v["eco_url"]
            }
            for k, v in sorted_openings[-5:]
        ]
    }

    return {
        "username": username,
        "month": f"{now.year}-{now.month:02d}",
        "summary": summary
    }
