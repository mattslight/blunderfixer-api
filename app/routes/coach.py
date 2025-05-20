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
    hero_side: Optional[str] = None  # 'w' or 'b'


class CoachResponse(BaseModel):
    reply: str
    messages: List[Message]


# ── System prompt builder ───────────────────────────────────────────────────────
def build_coach_system_prompt(
    fen: str,
    legal_moves: List[str],
    lines: List[LineInfo],
    features: Dict[str, Any],
    hero_side: str,
) -> str:
    feat = features or {}

    header = (
        "?? All evals & material figures are from White's POV:\n"
        "  - Positive = White ahead\n"
        "  - Negative = Black ahead\n\n"
    )

    perspective = "White" if hero_side.lower() == "w" else "Black"

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

    # positional summary with unambiguous material line using extractor 'balance' & 'advantage'
    mat = feat.get("material", {})
    bal = mat.get("balance", 0)
    adv = mat.get("advantage", "equal")
    summary = (
        "Position Features:\n"
        f"� Material (�pawns): {bal:+d} ({adv} by {abs(bal)} pawn"
        f"{'s' if abs(bal)!=1 else ''})\n"
        f"• King safety: White({feat.get('safety',{}).get('king',{}).get('white',{}).get('status','?')}), "
        f"Black({feat.get('safety',{}).get('king',{}).get('black',{}).get('status','?')})\n"
        f"• Open files: {', '.join(feat.get('lines',{}).get('open_files',[])) or 'none'}\n"
        f"• Passed pawns: White({wp or 'none'}), Black({bp or 'none'})\n"
        f"• Weak squares: White({wws or 'none'}), Black({bws or 'none'})\n"
        f"• Open diagonals: {', '.join(feat.get('lines',{}).get('diagonals',{}).get('open',[])) or 'none'}"
    )

    # lines block... prepend a reminder about eval‐sign before listing continuations
    eval_header = "Negative eval = Black better; Positive = White better\n"
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
    lines_block = eval_header + ("\n".join(line_texts) or "None")

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
You are coaching **{perspective}** in this game.
Your replies should be concise, actionable, and focused on practical advice.

🎯 Current Position (FEN): {fen}

{summary}

🧩 Position Highlights:
{highlight_text}

🧭 Top continuations:
{lines_block}

🔓 Legal Moves Allowed: {legal_moves_text}

{special}

{header}

🎯 REQUEST RULES:
- Whenever a specific move is mentioned, you **must** first check its eval by call `analyze_move_in_stockfish` *before* explaining.
- **Blend the eval, the principal variation, and the extracted features into a single cohesive insight.**  
For example:  
> After **Qb5**, Black's score of -1.27 reflects both the extra pawn and White's cramped queen-side.  
> Your passed pawn on d5 is a long-term asset, but your king's pawn shield is slightly weakened,  
> so exchanging queens now would concede that dynamic edge. 
- Whenever you suggest moves use **bold** formatting. When comparing moves, use a Markdown table with columns: Move | Pros | Cons.
- When the user mentions a move in free form (e.g. “bishop to e4 looks good”, “Is castles here good?”, “should I play c3?”):
  1. Try to parse it as SAN or castling:
     - Must match SAN grammar:  
       ^([KQRBN])?[a-h]?[1-8]?x?[a-h][1-8](=[QRBN])?[+#]?$  
       or ^O-O(-O)?$
  2. If it doesn’t match, reply:  
     “❓ I’m not familiar with that notation (‘Zf3’). Could you check the move and try again?”
  3. Otherwise, check if that SAN is in `legal_moves`:
     • If not, reply:  
       “⛔️ That move is not legal in this position.”  
       Then suggest 1–3 strong legal alternatives using a Markdown table with columns: Move | Pros | Cons.  
     • If it is, proceed to step 4.
  4. If more than one legal move could match a vague phrase (like “bishop takes”), ask:  
     “Which capture did you mean – **Bxd5** or **Bxe6**?”
  5. Once disambiguated:
     - If the move appears in 🧭 Top continuations, base your reply on that line.
     - Otherwise, call `analyze_move_in_stockfish`.
  6. If comparing two legal moves (e.g. “c3 or castles”), respond with a Markdown table with columns: Move | Pros | Cons. Do not use bullet points.
- If the user’s message starts with “Hint:”, give a subtle thematic nudge based on the 🧭 Top Continuations do not name the exact best move.
- If the user’s message begins with “Full analysis:”, provide:
  • A concise 3–5 sentence strategic overview.  
  • A Markdown table with columns: Move | Pros | Cons summarising the top continuations.
- Otherwise, answer the user’s free-form question directly, **using Markdown tables**.
- *** Never use bullets outside of rule formatting. ***


🧠 Focus on:
 - Draw on truths in your "why" explanations. Examples include, only talk about what is relevant to the position.
   - Material balance  
   - Passed pawns  
   - Space advantage  
   - King safety  
   - Weak squares  
   - Mobility & piece activity  
   - Any hanging/loose pieces  
- **Ultra-concise:** max 2 sentences per reply, no bullet lists
- Embed any “why” points directly in those sentences
- Bold key moves (e.g., **d4**, **Bc4**)
- Use light emojis 🎯🔥🏆 to highlight ideas
- If asked about a single move (e.g., "Is b4 good?"), start with a Quick Verdict:
    - ⭐️ Top / ✅ Good / ⚠️ Risky / ❌ Bad move etc. because...
    - Show the pros and cons in a Markdown table with columns: Move | Pros | Cons.
- If comparing moves (e.g., "c3 or castles"), use a Markdown table with columns: Move | Pros | Cons.
""".strip()


# ── Function spec for Stockfish ─────────────────────────────────────────────────
stockfish_fn = {
    "name": "analyze_move_in_stockfish",
    "description": (
        "Evaluate a single chess move (either SAN, e.g. 'Rc8', or UCI, e.g. 'a8c8') "
        "on a given FEN. Returns the resulting centipawn score, mate distance, "
        "and principal variation."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "fen": {"type": "string"},
            "move_str": {
                "type": "string",
                "description": "Move in SAN (e.g. 'Rc8') or UCI (e.g. 'a8c8')",
            },
            "depth": {"type": "integer", "default": 18},
            "multipv": {
                "type": "integer",
                "default": 1,
                "description": "How many PV lines to return; top line is used",
            },
            "top_lines": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "moves": {"type": "array", "items": {"type": "string"}},
                        "scoreCP": {"type": "integer"},
                    },
                    "required": ["moves", "scoreCP"],
                },
                "description": "Your pre-computed PVs & centipawn scores from the shallow engine pass",
            },
        },
        "required": ["fen", "move_str"],
    },
    "returns": {
        "type": "object",
        "properties": {
            "uci": {"type": "string"},
            "score_centipawns": {"type": "integer"},
            "mate": {"type": ["integer", "null"]},
            "delta": {
                "type": "integer",
                "description": "Score change vs. engine’s best move (negative = lost material)",
            },
            "verdict": {
                "type": "string",
                "description": "One of ⭐️ Top move, ✅ Good move, ⚠️ OK move, ⚠️ Risky move, ❌ Bad move",
            },
        },
        "required": ["uci", "score_centipawns", "mate", "delta", "verdict"],
    },
}


# ── Unified /coach endpoint ─────────────────────────────────────────────────────
router = APIRouter()


@router.post("/coach", response_model=CoachResponse)
def coach(req: CoachRequest):
    # # ── Debug printing ──────────────────────────────────────────────────────────
    # if DEBUG:
    #     print("🔔 /coach hit")
    #     print("  FEN:", req.fen)
    #     print("  user_message:", repr(req.user_message))

    # ── (A) Compute features & lines ────────────────────────────────────────────
    #  Features: server‐side unless overridden
    if req.features is None:
        features = extract_features(FeatureExtractionRequest(fen=req.fen))
    else:
        features = req.features

    #  Lines: use FE-supplied if present, otherwise quick fallback
    if req.lines is None:
        info_list = engine.analyse(
            chess.Board(req.fen), limit=chess.engine.Limit(depth=18), multipv=9
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

    # if DEBUG:
    #     print("  features keys:", list(features.keys()))
    #     print("  using lines:", [(l.rank, l.depth) for l in lines])

    # ── 1) Seed system prompt (only once) ──────────────────────────────────────
    if not any(m.role == "system" for m in req.past_messages):
        sys_msg = build_coach_system_prompt(
            req.fen, req.legal_moves, lines, features, req.hero_side or "w"
        )
        history = [Message(role="system", content=sys_msg)] + req.past_messages
    else:
        history = req.past_messages.copy()

    # ── 2) Append user turn ─────────────────────────────────────────────────────
    history.append(Message(role="user", content=req.user_message))

    # if DEBUG:
    #     # dump the entire system prompt
    #     print("SYSTEM PROMPT:\n", sys_msg, "\n" + "-" * 60)
    #     # or dump the full message list
    #     for m in history:
    #         print(f"{m.role.upper():8}: {m.name or ''} {m.content}")
    #     print("-" * 60)

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

        top_lines_payload = [
            {"moves": l.moves, "scoreCP": l.scoreCP, "rank": l.rank} for l in lines[:7]
        ]

        result = analyze_move_in_stockfish(
            fen=req.fen,
            move_str=args["move_str"],
            depth=args.get("depth", 18),
            multipv=args.get("multipv", 1),
            top_lines=top_lines_payload,
        )
        if DEBUG:
            print("  ? function result:", result)

        # Insert error handling before appending function result
        if "error" in result:
            # Gracefully handle analysis failure
            history.append(
                Message(
                    role="assistant",
                    content=f"?? Analysis unavailable: {result['error']}",
                )
            )
        else:
            history.append(Message(role="assistant", content=msg.content or ""))
            history.append(
                Message(
                    role="function",
                    name=msg.function_call.name,
                    content=json.dumps(result),
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
