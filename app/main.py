from fastapi import FastAPI
from pydantic import BaseModel

app = FastAPI()

class AnalyzeRequest(BaseModel):
    fen: str

@app.get("/health")
def health_check():
    return {"status": "ok"}

@app.post("/analyze")
def analyze_fen(req: AnalyzeRequest):
    # TEMP MOCK: This will be replaced with real Stockfish eval
    return {
        "fen": req.fen,
        "best_move": "e2e4",
        "evaluation": "+0.34 (mocked)"
    }

