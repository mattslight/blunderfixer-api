import json
import requests
from pathlib import Path
import chess.pgn
import io
from collections import Counter, defaultdict

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

def summarize_games(games: list, username: str) -> dict:
    summary = {
        "total_games": 0,
        "wins": 0,
        "losses": 0,
        "draws": 0,
        "time_classes": {},
        "avg_moves": 0,
        "win_types": {"checkmated": 0, "abandoned": 0, "timeout": 0, "resigned": 0, "unknown": 0},  # Track win types
        "loss_types": {"checkmated": 0, "abandoned": 0, "timeout": 0, "resigned": 0, "unknown": 0}  # Track loss types

    }

    total_moves = 0
    opening_counter = Counter()
    openings = defaultdict(lambda: {"games": 0, "wins": 0, "losses": 0, "draws": 0, "hero_color": "", "eco": "", "eco_url": ""})

    for game in games:
        summary["total_games"] += 1

        # Determine result and win/loss type for the user (white or black)
        result = ""
        result_outcome = "unknown"
        if game["white"]["username"].lower() == game["url"].split('/')[-1].lower():  # If it's the white player
            result = game["white"].get("result", "")
            result_outcome = game["black"].get("result", "unknown")
        else:  # It's the black player
            result = game["black"].get("result", "")
            result_outcome = game["white"].get("result", "unknown")

        # Update win/loss based on result
        if result == "win":
            summary["wins"] += 1
            summary["win_types"][result_outcome] += 1
        elif result in ("checkmated", "timeout", "resigned", "lose", "abandoned"):
            summary["losses"] += 1
            summary["loss_types"][result] += 1
        elif result == "agreed":
            summary["draws"] += 1

        # Time class (blitz, rapid, etc.)
        tc = game.get("time_class", "unknown")
        summary["time_classes"][tc] = summary["time_classes"].get(tc, 0) + 1

        # PGN parsing for Move count etc.
        pgn_text = game.get("pgn", "")
        game_obj = chess.pgn.read_game(io.StringIO(pgn_text))

        if game_obj is not None:
            move_count = sum(1 for _ in game_obj.mainline())
            total_moves += move_count

            # Use Chess.com provided opening name or ECO code
            eco = game_obj.headers.get("ECO", "Unknown")
            eco_url = game_obj.headers.get("ECOUrl", "")
            if "openings/" in eco_url:
                name = eco_url.split("openings/")[-1].replace("-", " ").title()
            else:
                name = "Unknown Opening"

            opening_key = f"{name} ({eco})"
            opening_counter[opening_key] += 1
            openings[opening_key]["games"] += 1

            # Determine hero color (white or black)
            if game["white"]["username"].lower() == username.lower():
                openings[opening_key]["hero_color"] = "white"
            elif game["black"]["username"].lower() == username.lower():
                openings[opening_key]["hero_color"] = "black"
            else:
                openings[opening_key]["hero_color"] = "unknown"  # Just in case, default to unknown


            # Add ECO and ECO URL
            openings[opening_key]["eco"] = eco
            openings[opening_key]["eco_url"] = eco_url

            if result == "win":
                openings[opening_key]["wins"] += 1
            elif result in ("checkmated", "timeout", "resigned", "lose", "abandoned"):
                openings[opening_key]["losses"] += 1
            elif result == "agreed":
                openings[opening_key]["draws"] += 1

    summary["avg_moves"] = round((total_moves / summary["total_games"]) / 2, 1) if summary["total_games"] else 0
    summary["training_suggestion"] = "Review key endgames with exposed kings"

    # Add most common opening
    most_common = opening_counter.most_common(1)
    summary["most_common_opening"] = most_common[0][0] if most_common else "unknown"

    # Add hero color and ECO info to each opening
    for stats in openings.values():
        g = stats["games"]
        w = stats["wins"]
        stats["win_rate"] = round((w / g) * 100, 1) if g else 0.0

    return summary, dict(openings)  # Return both summary and openings data

