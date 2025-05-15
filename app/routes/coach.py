# app/routers/coach.py

import json
import os
from typing import Any, Dict, List, Optional

import chess
import chess.engine
from fastapi import APIRouter, HTTPException
from openai import OpenAI
from pydantic import BaseModel

from app.utils.stockfish import analyze_move_in_stockfish

from .fen_feature_extraction import FeatureExtractionRequest, extract_features

# ── Simple debug flag ───────────────────────────────────────────────────────────
DEBUG = os.getenv("DEBUG", "").lower() in ("1", "true", "yes")
if DEBUG:
    print("🚀 DEBUG enabled")

# ── OpenAI client ───────────────────────────────────────────────────────────────
api_key = os.getenv("OPENAI_API_KEY")
if not api_key:
    raise HTTPException(500, "OpenAI API key not set.")
client = OpenAI(api_key=api_key)

# ── Stockfish engine ────────────────────────────────────────────────────────────
ENGINE_PATH = os.getenv("STOCKFISH_PATH", "/usr/bin/stockfish")
engine = chess.engine.SimpleEngine.popen_uci(ENGINE_PATH)


# ── Pydantic models ─────────────────────────────────────────────────────────────
class Message(BaseModel):
    role: str
    name: Optional[str] = None  # allow name on function messages
    content: str


class LineInfo(BaseModel):
    moves: List[str]
    scoreCP: Optional[int]
    mateIn: Optional[int]
    depth: int
    rank: int


class CoachRequest(BaseModel):
    fen: str
    past_messages: List[Message]
    user_message: str
    legal_moves: List[str]
    lines: Optional[List[LineInfo]] = None
    features: Optional[Dict[str, Any]] = None


class CoachResponse(BaseModel):
    reply: str
    messages: List[Message]


# ── System prompt builder ───────────────────────────────────────────────────────
def build_coach_system_prompt(
    fen: str,
    legal_moves: List[str],
    lines: List[LineInfo],
    features: Dict[str, Any],
) -> str:
    feat = features or {}

    # highlights...
    highlights = []
    wp = ", ".join(feat.get("structure", {}).get("passed_pawns", {}).get("white", []))
    bp = ", ".join(feat.get("structure", {}).get("passed_pawns", {}).get("black", []))
    if wp or bp:
        highlights.append(
            f"Passed pawns — White({wp or 'none'}), Black({bp or 'none'})"
        )

    wws = ", ".join(feat.get("safety", {}).get("weak_squares", {}).get("white", []))
    bws = ", ".join(feat.get("safety", {}).get("weak_squares", {}).get("black", []))
    if wws or bws:
        highlights.append(
            f"Weak squares — White({wws or 'none'}), Black({bws or 'none'})"
        )

    of = ", ".join(feat.get("lines", {}).get("open_files", []))
    if of:
        highlights.append(f"Open files — {of}")

    sodw = ", ".join(
        feat.get("lines", {}).get("diagonals", {}).get("semi_open_white", [])
    )
    sodb = ", ".join(
        feat.get("lines", {}).get("diagonals", {}).get("semi_open_black", [])
    )
    if sodw or sodb:
        highlights.append(
            f"Semi-open diagonals — White({sodw or 'none'}), Black({sodb or 'none'})"
        )

    highlight_text = " • ".join(highlights) if highlights else "None"

    # positional summary...
    summary = (
        f"Position Features:\n"
        f"• Material: {feat.get('material', {}).get('advantage','?')} "
        f"{feat.get('material',{}).get('balance','?')}\n"
        f"• King safety: White({feat.get('safety',{}).get('king',{}).get('white',{}).get('status','?')}), "
        f"Black({feat.get('safety',{}).get('king',{}).get('black',{}).get('status','?')})\n"
        f"• Open files: {', '.join(feat.get('lines',{}).get('open_files',[])) or 'none'}\n"
        f"• Passed pawns: White({wp or 'none'}), Black({bp or 'none'})\n"
        f"• Weak squares: White({wws or 'none'}), Black({bws or 'none'})\n"
        f"• Open diagonals: {', '.join(feat.get('lines',{}).get('diagonals',{}).get('open',[])) or 'none'}"
    )

    # lines block...
    line_texts = []
    for ln in lines:
        score = (
            f"{ln.scoreCP/100:.2f}"
            if ln.scoreCP is not None
            else f"mate in {ln.mateIn}"
        )
        snippet = " → ".join(ln.moves[:5])
        suffix = " …" if len(ln.moves) > 5 else ""
        line_texts.append(
            f"#{ln.rank} (depth {ln.depth}) | Eval: {score} | Line: {snippet}{suffix}"
        )
    lines_block = "\n".join(line_texts) or "None"

    legal_moves_text = ", ".join(legal_moves) if legal_moves else "No legal moves"

    special = ""
    if len(legal_moves) == 1:
        special = (
            f"🚨 Special Situation:\n"
            f"There is **only one legal move**: **{legal_moves[0]}**.\n"
            "Highlight urgently that this is the only survival move."
        )

    return f"""
You are a world-class chess coach advising club-level players (rating 800–1800).
Your replies should be concise, actionable, and focused on practical advice.

🎯 Current Position (FEN): {fen}

{summary}

🧩 Position Highlights:
{highlight_text}

🧭 Top continuations:
{lines_block}

🔓 Legal Moves Allowed: {legal_moves_text}

{special}

🎯 REQUEST RULES:
- If the user asks about a move in free form (e.g. “Is castles here good?”, “What about bishop takes?”):
  1. Look at your `legal_moves` list and filter for any that match the user’s phrase:
     - For “castles”, match `O-O` and `O-O-O`.
     - For “bishop takes”, match any SAN that starts with `B` and contains `x`.
  2. If exactly **one** candidate remains, treat that as the move and proceed to step 3.
  3. If **multiple** candidates remain, ask a brief clarifying question:
     “Which capture did you mean – **Bxd5** or **Bxe6**?”
  4. Once disambiguated,
     - only call analyze_move_in_stockfish if that UCI is **not** present in 🧭  Top continuations. 
     - If it **is** present, base your reply on the corresponding line.
- If user message starts with "Hint:", give a subtle nudge based on themes of the line—do NOT name the exact best move or give a direct hint.
- If the user’s message begins with “Full analysis:”, respond with:
  • A concise 3–5 sentence strategic overview.
  • A Markdown table with columns Move | Pros | Cons summarizing the top continuations.
- Otherwise, answer the user's free-form question directly.

🧠 Focus on:
- Practical, actionable advice
- Short replies (2–4 sentences)
- Bold key moves (e.g., **d4**, **Bc4**)
- Use light emojis 🎯🔥🏆 to highlight ideas
- If asked about a move (e.g., "Is b4 good?"), start with a Quick Verdict:
    - ✅ Good idea because...
    - ⚠️ Risky move because...
""".strip()


# ── Function spec for Stockfish ─────────────────────────────────────────────────
stockfish_fn = {
    "name": "analyze_move_in_stockfish",
    "description": (
        "Evaluate whether a single UCI move is good or bad by returning "
        "the centipawn score and mate information."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "fen": {"type": "string"},
            "uci": {"type": "string"},
            "depth": {"type": "integer", "default": 20},
            "multipv": {"type": "integer", "default": 3},
        },
        "required": ["fen", "uci"],
    },
    "returns": {
        "type": "object",
        "properties": {
            "uci": {"type": "string"},
            "single_move_score": {"type": "integer"},
            "single_move_mate": {"type": ["integer", "null"]},
            "lines": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "moves": {"type": "array", "items": {"type": "string"}},
                        "score_centipawns": {"type": "integer"},
                        "mate": {"type": ["integer", "null"]},
                        "depth": {"type": "integer"},
                        "multipv_rank": {"type": "integer"},
                    },
                    "required": [
                        "moves",
                        "score_centipawns",
                        "mate",
                        "depth",
                        "multipv_rank",
                    ],
                },
            },
        },
        "required": ["uci", "single_move_score", "lines"],
    },
}

# ── Unified /coach endpoint ─────────────────────────────────────────────────────
router = APIRouter()


@router.post("/coach", response_model=CoachResponse)
def coach(req: CoachRequest):
    # ── Debug printing ──────────────────────────────────────────────────────────
    if DEBUG:
        print("🔔 /coach hit")
        print("  FEN:", req.fen)
        print("  user_message:", repr(req.user_message))

    # ── (A) Compute features & lines ────────────────────────────────────────────
    #  Features: server‐side unless overridden
    if req.features is None:
        features = extract_features(FeatureExtractionRequest(fen=req.fen))
    else:
        features = req.features

    #  Lines: use FE-supplied if present, otherwise quick fallback
    if req.lines is None:
        info_list = engine.analyse(
            chess.Board(req.fen), limit=chess.engine.Limit(depth=12), multipv=3
        )
        lines: List[LineInfo] = []
        for idx, info in enumerate(info_list, start=1):
            pov = info["score"].pov(chess.Board(req.fen).turn)
            pv = info.get("pv", [])
            lines.append(
                LineInfo(
                    moves=[mv.uci() for mv in pv],
                    scoreCP=pov.score(mate_score=1_000_000),
                    mateIn=pov.mate(),
                    depth=info["depth"],
                    rank=idx,
                )
            )
    else:
        lines = req.lines

    if DEBUG:
        print("  features keys:", list(features.keys()))
        print("  using lines:", [(l.rank, l.depth) for l in lines])

    # ── 1) Seed system prompt (only once) ──────────────────────────────────────
    if not any(m.role == "system" for m in req.past_messages):
        sys_msg = build_coach_system_prompt(req.fen, req.legal_moves, lines, features)
        history = [Message(role="system", content=sys_msg)] + req.past_messages
    else:
        history = req.past_messages.copy()

    # ── 2) Append user turn ─────────────────────────────────────────────────────
    history.append(Message(role="user", content=req.user_message))

    if DEBUG:
        # dump the entire system prompt
        print("SYSTEM PROMPT:\n", sys_msg, "\n" + "-" * 60)
        # or dump the full message list
        for m in history:
            print(f"{m.role.upper():8}: {m.name or ''} {m.content}")
        print("-" * 60)

    # ── 3) First LLM call (with function‐calling) ───────────────────────────────
    resp = client.chat.completions.create(
        model="gpt-4o",
        messages=[m.dict() for m in history],
        functions=[stockfish_fn],
        function_call="auto",
        temperature=0.3,
    )
    msg = resp.choices[0].message

    # ── 4) If model asks to call Stockfish… ────────────────────────────────────
    if msg.function_call:
        raw_args = msg.function_call.arguments
        try:
            args = json.loads(raw_args) if isinstance(raw_args, str) else raw_args
        except json.JSONDecodeError:
            raise HTTPException(500, f"Invalid function arguments: {raw_args!r}")

        if DEBUG:
            print("  → function call:", msg.function_call.name, args)

        result = analyze_move_in_stockfish(args["fen"], args["uci"])
        if DEBUG:
            print("  ← function result:", result)

        history.append(Message(role="assistant", content=msg.content or ""))
        history.append(
            Message(
                role="function", name=msg.function_call.name, content=json.dumps(result)
            )
        )

        # 5) Follow-up LLM call
        follow = client.chat.completions.create(
            model="gpt-4o",
            messages=[m.dict() for m in history],
            temperature=0.3,
        )
        reply = follow.choices[0].message.content.strip()
        history.append(Message(role="assistant", content=reply))

    else:
        # Plain text reply
        reply = msg.content.strip()
        history.append(Message(role="assistant", content=reply))

    if DEBUG:
        print("✅ Coach reply:", reply)

    return CoachResponse(reply=reply, messages=history)
