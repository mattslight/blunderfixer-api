from fastapi import APIRouter
from app.schemas import AnalyseRequest
from app.engine import analyse_fen

router = APIRouter()

@router.post("/analyse-fen",
             summary="Analyse FEN Position",
             description="Returns Stockfish evaluation and best move for a given FEN string.")
def analyse_fen_endpoint(req: AnalyseRequest):
    result = analyse_fen(req.fen, top_n=req.top_n)

    if "error" in result:
        return {"error": result["error"]}

    return result
