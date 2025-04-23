import json
import requests
from datetime import datetime
from pathlib import Path
import chess.pgn
import io

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

def summarize_games(games: list) -> dict:
    summary = {
        "total_games": 0,
        "wins": 0,
        "losses": 0,
        "draws": 0,
        "time_classes": {},
        "avg_moves": 0,
    }

    total_moves = 0

    for game in games:
        summary["total_games"] += 1

        # Determine result
        result = ""
        if game["white"]["username"].lower() == game["url"].split('/')[-1].lower():
            result = game["white"].get("result", "")
        else:
            result = game["black"].get("result", "")

        if result == "win":
            summary["wins"] += 1
        elif result in ("checkmated", "timeout", "resigned", "lose", "abandoned"):
            summary["losses"] += 1
        elif result == "agreed":
            summary["draws"] += 1

        # Time class
        tc = game.get("time_class", "unknown")
        summary["time_classes"][tc] = summary["time_classes"].get(tc, 0) + 1

        # Move count
        pgn_text = game.get("pgn", "")
        game_obj = chess.pgn.read_game(io.StringIO(pgn_text))

        if game_obj is not None:
            move_count = sum(1 for _ in game_obj.mainline())
            total_moves += move_count

    summary["avg_moves"] = round(total_moves / summary["total_games"] / 2, 1) if summary["total_games"] else 0

    # Optional training suggestion (placeholder for now)
    summary["training_suggestion"] = "Review key endgames with exposed kings"

    return summary
