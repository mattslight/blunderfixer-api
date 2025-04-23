from fastapi import APIRouter
from app.schemas import AnalyzeRequest
from app.engine import analyze_fen

router = APIRouter()

@router.post("/analyze")
def analyze_fen_endpoint(req: AnalyzeRequest):
    result = analyze_fen(req.fen, top_n=req.top_n)

    if "error" in result:
        return {"error": result["error"]}

    return result
