from fastapi import FastAPI
from pydantic import BaseModel

app = FastAPI()

class AnalyzeRequest(BaseModel):
    fen: str

@app.get("/health")
def health_check():
    return {"status": "ok"}

from app.engine import analyze_fen

@app.post("/analyze")
def analyze_fen_endpoint(req: AnalyzeRequest):
    result = analyze_fen(req.fen)
    return {
        "fen": req.fen,
        "best_move": result["best_move"],
        "evaluation": result["evaluation"]
    }
