from fastapi import FastAPI
from pydantic import BaseModel
from app.engine import analyze_fen

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
