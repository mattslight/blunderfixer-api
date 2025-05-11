import logging
import os
from typing import Any, Dict, List

import openai
from dotenv import load_dotenv
from fastapi import APIRouter, HTTPException

from app.schemas import ExplanationRequest  # New schema needed
from app.schemas import LineInfo

load_dotenv()
router = APIRouter()

DEBUG = os.getenv("DEBUG", "").lower() in ("1", "true", "yes")

# configure a logger
logger = logging.getLogger(__name__)
handler = logging.StreamHandler()
handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
logger.addHandler(handler)
logger.setLevel(logging.DEBUG if DEBUG else logging.INFO)

# configue open ai
openai_api_key = os.getenv("OPENAI_API_KEY")
if not openai_api_key:
    raise HTTPException(
        status_code=500, detail="Server misconfiguration: OpenAI API key not set."
    )

client = openai.OpenAI(api_key=openai_api_key)


# handle router request
@router.post("/explain-lines", summary="Get Coach Explanation")
def get_explanation(req: ExplanationRequest):
    prompt = build_prompt(req.fen, req.lines, req.legal_moves, req.features)
    # log the exact prompt when DEBUG=1
    logger.debug("📝 [DEBUG] Prompt sent to LLM:\n%s", prompt)

    try:
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
            max_completion_tokens=200,
            frequency_penalty=0.5,
            presence_penalty=0.0,
        )
        # log the entire raw response object in DEBUG
        # logger.debug("📦 [DEBUG] Raw LLM response:\n%s", response)
        explanation = response.choices[0].message.content
        logger.info("🧠 Explanation Response: %s", explanation)
        return {"explanation": explanation}
    except Exception as e:
        logger.error("🔥 Error during OpenAI call: %s", e, exc_info=DEBUG)
        return {"error": str(e)}


def build_prompt(
    fen: str, lines: List[LineInfo], legal_moves: List[str], features: Dict[str, Any]
) -> str:
    feat = features

    # 0) Build a concise “Highlights” of non-obvious features
    highlights = []
    # passed pawns
    wp = ", ".join(feat["structure"]["passed_pawns"]["white"])
    bp = ", ".join(feat["structure"]["passed_pawns"]["black"])
    if wp or bp:
        highlights.append(
            f"Passed pawns — White({wp or 'none'}), Black({bp or 'none'})"
        )
    # weak squares
    wws = ", ".join(feat["safety"]["weak_squares"]["white"])
    bws = ", ".join(feat["safety"]["weak_squares"]["black"])
    if wws or bws:
        highlights.append(
            f"Weak squares — White({wws or 'none'}), Black({bws or 'none'})"
        )
    # open files
    of = ", ".join(feat["lines"]["open_files"])
    if of:
        highlights.append(f"Open files — {of}")
    # semi-open diagonals
    sodw = ", ".join(feat["lines"]["diagonals"]["semi_open_white"])
    sodb = ", ".join(feat["lines"]["diagonals"]["semi_open_black"])
    if sodw or sodb:
        highlights.append(
            f"Semi-open diagonals for White({sodw or 'none'}), Black({sodb or 'none'})"
        )

    highlight_text = " • ".join(highlights) if highlights else "None"

    # 1) Build a bullet‐list summary of the key positional features
    summary = f"""
    Position Features:
    • Material: {feat['material']['advantage']} {feat['material']['balance']}
    • King safety: White({feat['safety']['king']['white']['status']}), Black({feat['safety']['king']['black']['status']})
    • Open files: {', '.join(feat['lines']['open_files']) or 'none'}
    • Passed pawns: White({', '.join(feat['structure']['passed_pawns']['white'])}), Black(...)
    • Weak squares: {feat['safety']['weak_squares']}
    • Open diagonals: {', '.join(feat['lines']['diagonals']['open'])}
    """

    # 2) Show a summary table of each line:
    line_texts = []
    for ln in lines:
        score = (
            f"{ln.scoreCP/100:.2f}"
            if ln.scoreCP is not None
            else f"mate in {ln.mateIn}"
        )
        moves_snippet = " → ".join(ln.moves[:5])
        line_texts.append(
            f"#{ln.rank} (depth {ln.depth}) | Eval: {score} | Line: {moves_snippet}{' …' if len(ln.moves)>5 else ''}"
        )
    lines_block = "\n".join(line_texts)

    # 3) Construct the legal moves text
    legal_moves_text = ", ".join(legal_moves) if legal_moves else "No legal moves"

    # 3) Any special instructions for single‐move situations
    special_instructions = ""
    # 🧠 Inject extra coaching if only 1 legal move
    if len(legal_moves) == 1:
        special_instructions = f"""
        🚨 Special Situation:
        There is **only one legal move**: **{legal_moves[0]}**.
        The player is likely in check or facing immediate threats.
        Your explanation MUST highlight that this is the **only move** to survive or avoid immediate loss.
        Be clear, urgent, but still encouraging.
        """

    prompt = f"""
            You are a world-class chess coach advising club-level players (rating 800–1800).

            Your goal is to explain the position **clearly and concisely** without unnecessary introductions or filler – **pay particular attention to the top continuations**.

            FEN: {fen}

            {summary}

            🧩 **Position Highlights:**  
            {highlight_text}

            🧭 **Top continuations** (showing rank, depth, eval, first few moves):
            {lines_block}

            🔓 **Legal Moves Allowed:**
            {legal_moves_text}

            {special_instructions}

            🎯 **Your writing rules:**
            1. Start immediately with the best move recommendation (no greetings or intros).
            2. BE CONCISE AND DIRECT
            3. **Short paragraphs** (2–3 sentences each).
            4. **Bold important moves** (e.g., **d4**, **Bc4**). Use Standard Algebraic Notation (SAN) only.
            5. Use emojis lightly to emphasize key ideas (🎯 tactics, 🔥 attacks, 🏰 castling etc.)
            6. Include a Quick Table (| Move | Pros | Cons |) if comparing moves.
            7. Focus on 1–2 key positional or tactical ideas.

            ❌ Avoid:
            1. No UCI in narrative `b1a2`
            2. No "In this intriguing position..."
            3. No "You have a wonderful opportunity..."
            4. No long-winded openings.
            5. No vague generalities. Avoid "Stay vigilant", "look for tactics", "Keep the pressure", "find weaknesses" to exploit", "every move counts!"
            6. No robotic listing of moves without ideas.

            🏁 Coach with energy, precision, and clarity.

            ⚠️ **RESPONSE REQUIREMENTS:**  
            - **Max 5 sentences**
            - **Include Quick Table**  
            - **Under 150 words**  
            """
    return prompt
