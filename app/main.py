from fastapi import FastAPI
from pydantic import BaseModel
from app.engine import analyze_fen
from datetime import datetime
from app.utils import get_games

app = FastAPI()

class AnalyzeRequest(BaseModel):
    fen: str
    top_n: int = 1

@app.get("/health")
def health_check():
    return {"status": "ok"}

@app.post("/analyze")
def analyze_fen_endpoint(req: AnalyzeRequest):
    result = analyze_fen(req.fen, top_n=req.top_n)

    if "error" in result:
        return {"error": result["error"]}

    return result  # This now returns {'fen': ..., 'top_moves': [...]}

@app.get("/games/{username}")
def fetch_games(username: str):
    now = datetime.utcnow()
    games = get_games(username, now.year, now.month)
    return {
        "username": username,
        "month": f"{now.year}-{now.month:02d}",
        "games_fetched": len(games),
        "games": games
    }