import json
import requests
from pathlib import Path

BASE_DATA_DIR = Path("data")

def get_games(username: str, year: int, month: int) -> list:
    user_dir = BASE_DATA_DIR / username.lower()
    user_dir.mkdir(parents=True, exist_ok=True)

    month_str = f"{year}-{month:02d}"
    json_path = user_dir / f"{month_str}.json"

    if json_path.exists():
        with open(json_path, "r") as f:
            return json.load(f)

    # Fetch from Chess.com
    url = f"https://api.chess.com/pub/player/{username}/games/{year}/{month:02d}"
    headers = {
        "User-Agent": "Mozilla/5.0"
    }
    print(f"Fetching from {url}")
    resp = requests.get(url, headers=headers)
    if resp.status_code != 200:
        raise Exception(f"Failed to fetch games for {username}: {resp.status_code}")

    games = resp.json().get("games", [])

    # Always save this month
    with open(json_path, "w") as f:
        json.dump(games, f, indent=2)

    return games