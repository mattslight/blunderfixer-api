import httpx
from fastapi import APIRouter, HTTPException, Query

router = APIRouter(prefix="/public")

def normalize_player(p):
    # If it's a dict, extract all known keys
    if isinstance(p, dict):
        return {
            "username": p.get("username"),
            "rating":   p.get("rating"),
            "result":   p.get("result"),
            "@id":      p.get("@id"),
            "uuid":     p.get("uuid"),
        }
    # Otherwise it's just the username string
    return {"username": p}

@router.get("/players/{username}/recent-games")
async def recent_games(
    username: str,
    limit: int = Query(20, ge=1, le=50),
):
    async with httpx.AsyncClient(timeout=10.0) as client:
        recent = []
        # 1) today’s games
        daily = await client.get(f"https://api.chess.com/pub/player/{username}/games")
        if daily.status_code == 200:
            today = daily.json().get("games", [])
            recent.extend(today[:limit])   

        # 2) fill up from monthly archives
        if len(recent) < limit:
            resp = await client.get(f"https://api.chess.com/pub/player/{username}/games/archives")
            if resp.status_code != 200:
                raise HTTPException(resp.status_code, "Could not fetch archives")
            for url in reversed(resp.json().get("archives", [])):
                r = await client.get(url)
                if r.status_code != 200:
                    continue
                recent.extend(r.json().get("games", []))
                if len(recent) >= limit:
                    break

    # 2.5) make sure the very latest games are at the front
    recent.sort(key=lambda g: g.get("end_time", 0), reverse=True)

    # 3) map into your full shape, using normalize_player()
    out = []
    for g in recent[:limit]:
        out.append({
            "url":           g.get("url"),
            "pgn":           g.get("pgn"),
            "time_control":  g.get("time_control"),
            "rated":         g.get("rated"),
            "tcn":           g.get("tcn"),
            "uuid":          g.get("uuid"),
            "initial_setup": g.get("initial_setup"),
            "fen":           g.get("fen"),
            "time_class":    g.get("time_class"),
            "rules":         g.get("rules"),
            "end_time":      g.get("end_time"),
            "termination":   g.get("termination"),
            "white":         normalize_player(g.get("white")),
            "black":         normalize_player(g.get("black")),
        })

    return out
