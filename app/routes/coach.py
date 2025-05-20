# app/routers/coach.py
import logging
from typing import Any, Dict, List, Literal

import chess
from agents import Agent, Runner, function_tool
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.utils.stockfish import analyze_move_in_stockfish

from .fen_feature_extraction import FeatureExtractionRequest, extract_features

# Configure logger
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s"
)
router = APIRouter()


# --- Request/Response Models ----------------------------------------------
class AgentCoachRequest(BaseModel):
    fen: str
    past_messages: List[Dict[str, str]]  # each dict has 'role' and 'content'
    user_message: str
    hero_side: Literal["w", "b"]

    class Config:
        extra = "ignore"


class AgentCoachResponse(BaseModel):
    reply: str


# --- Tool definitions with logging ----------------------------------------
@function_tool
def classify_intent(message: str) -> Dict[str, Any]:
    import re

    pattern = r"([KQRBN]?[a-h]?[1-8]?x?[a-h][1-8](=[QRBN])?[+#]?)"
    found = re.findall(pattern, message)
    ambiguous = " or " in message.lower() or len(found) > 1
    intent = (
        "compare_moves" if ambiguous else ("single_move" if found else "general_query")
    )
    return {"intent": intent, "moves": found, "ambiguous": ambiguous}


@function_tool
def check_legal(fen: str, moves: List[str]) -> Dict[str, Any]:
    board = chess.Board(fen)
    legal, illegal = [], []
    for m in moves:
        try:
            mv = chess.Move.from_uci(m) if len(m) == 4 else board.parse_san(m)
            (legal if mv in board.legal_moves else illegal).append(m)
        except Exception:
            illegal.append(m)
    return {"legal_moves": legal, "illegal_moves": illegal}


@function_tool
def summarize_position(fen: str) -> Dict[str, Any]:
    logging.info(f"[Tool summarize_position] fen={fen}")
    feats: Dict[str, Any] = extract_features(FeatureExtractionRequest(fen=fen))
    # Build concise bullets from the feature dict
    bullets = [
        f"Material: {feats['material']['balance']:+d} ({feats['material']['advantage']}).",
        f"King safety: White({feats['safety']['king']['white']['status']}), "
        f"Black({feats['safety']['king']['black']['status']}).",
        f"Passed pawns: White({', '.join(feats['structure']['passed_pawns']['white']) or 'none'}), "
        f"Black({', '.join(feats['structure']['passed_pawns']['black']) or 'none'}).",
        f"Weak squares: White({', '.join(feats['safety']['weak_squares']['white']) or 'none'}), "
        f"Black({', '.join(feats['safety']['weak_squares']['black']) or 'none'}).",
    ]
    return {"bullets": bullets, "raw": feats}


@function_tool
def analyze_moves_stockfish(
    fen: str, moves: List[str], depth: int = 12
) -> List[Dict[str, Any]]:
    out = []
    for m in moves:
        res = analyze_move_in_stockfish(fen=fen, move_str=m, depth=depth)
        out.append(res)
    return out


@function_tool
def generate_variation(fen: str, move: str, depth: int = 12) -> Dict[str, Any]:
    res = analyze_move_in_stockfish(fen=fen, move_str=move, depth=depth, multipv=1)
    return {"variation": res.get("pv", [])}


# --- Agent instantiation ---------------------------------------------------
coach_agent = Agent(
    name="ChessCoachAgent",
    instructions="""
You are a world-class club-level chess coach.
On every user turn, you **must** first call summarize_position(fen=context.fen) before replying.

The call returns:
- `bullets`: concise highlights.
- `raw`: full feature dict with keys material, center_control, safety, structure, mobility,
  space_advantage, tactics, lines.

Use `bullets` for overview and reference `raw` for details when needed.
Then classify intent, check legality, analyze moves, and reply in Markdown:
- Bold moves
- Tables for comparisons
- Quick verdicts for single moves
- Thematic hints for prefixes "Hint:"
- Full analysis for "Full analysis:"
""",
    tools=[
        classify_intent,
        check_legal,
        summarize_position,
        analyze_moves_stockfish,
        generate_variation,
    ],
)


# --- /coach endpoint -------------------------------------------------------
@router.post("/coach", response_model=AgentCoachResponse)
async def coach(req: AgentCoachRequest):
    # Debug incoming request
    logging.info(f"[DEBUG] /coach payload: {req.json()}")

    # Precompute summary to inject into context
    feats = extract_features(FeatureExtractionRequest(fen=req.fen))
    bullets = [
        f"Material: {feats['material']['balance']:+d} ({feats['material']['advantage']}).",
        f"King safety: White({feats['safety']['king']['white']['status']}), "
        f"Black({feats['safety']['king']['black']['status']}).",
        f"Passed pawns: White({', '.join(feats['structure']['passed_pawns']['white']) or 'none'}), "
        f"Black({', '.join(feats['structure']['passed_pawns']['black']) or 'none'}).",
        f"Weak squares: White({', '.join(feats['safety']['weak_squares']['white']) or 'none'}), "
        f"Black({', '.join(feats['safety']['weak_squares']['black']) or 'none'}).",
    ]
    logging.info(f"[DEBUG] Precomputed bullets: {bullets}")

    # Assemble system messages
    fen_msg = {"role": "system", "content": f"FEN: {req.fen}"}
    side_msg = {"role": "system", "content": f"Hero side: {req.hero_side}"}
    summary_msg = {"role": "system", "content": f"Position summary: {bullets}"}
    full_history = [fen_msg, side_msg, summary_msg] + req.past_messages
    logging.info(f"[🍎] Context for agent: {full_history}")

    try:
        result = await Runner.run(
            coach_agent,
            req.user_message,
            context={
                "history": full_history,
                "features": feats,
                "bullets": bullets,
                "fen": req.fen,
                "hero_side": req.hero_side,
            },
        )
        logging.info(f"[DEBUG] Agent.run result: {result!r}")
    except Exception:
        logging.exception("Error in /coach endpoint")
        raise HTTPException(status_code=500, detail="Internal error")

    return {"reply": result.final_output}
