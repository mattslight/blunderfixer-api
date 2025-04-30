import openai
from fastapi import APIRouter, HTTPException
from app.schemas import ExplanationRequest  # New schema needed
from dotenv import load_dotenv

import os

load_dotenv()
router = APIRouter()

openai_api_key = os.getenv("OPENAI_API_KEY")
if not openai_api_key:
    raise HTTPException(status_code=500, detail="Server misconfiguration: OpenAI API key not set.")

client = openai.OpenAI(api_key=openai_api_key)

@router.post("/explain-lines", summary="Get Coach Explanation")
def get_explanation(req: ExplanationRequest):
    prompt = build_prompt(req.fen, req.top_moves, req.legal_moves, req.features)

    try:
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.7,
            max_tokens=500
        )
        explanation = response.choices[0].message.content
        print("🧠 Explanation Response:", explanation)
        return {"explanation": explanation}
    except Exception as e:
        print("🔥 Error during OpenAI call:", str(e))
        return {"error": str(e)}


def build_prompt(fen: str, top_moves: list, legal_moves: list, features: dict) -> str:
    feat = features

    # 0) Build a concise “Highlights” of non-obvious features
    highlights = []
    # passed pawns
    wp = ", ".join(feat['structure']['passed_pawns']['white'])
    bp = ", ".join(feat['structure']['passed_pawns']['black'])
    if wp or bp:
        highlights.append(f"Passed pawns — White({wp or 'none'}), Black({bp or 'none'})")
    # weak squares
    wws = ", ".join(feat['safety']['weak_squares']['white'])
    bws = ", ".join(feat['safety']['weak_squares']['black'])
    if wws or bws:
        highlights.append(f"Weak squares — White({wws or 'none'}), Black({bws or 'none'})")
    # open files
    of = ", ".join(feat['lines']['open_files'])
    if of:
        highlights.append(f"Open files — {of}")
    # semi-open diagonals
    sodw = ", ".join(feat['lines']['diagonals']['semi_open_white'])
    sodb = ", ".join(feat['lines']['diagonals']['semi_open_black'])
    if sodw or sodb:
        highlights.append(f"Semi-open diagonals for White({sodw or 'none'}), Black({sodb or 'none'})")

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

    # 2) Prepare the top‐moves text
    move_texts = []
    for move in top_moves:
        line_preview = " → ".join(move.line[:5]) + (" ..." if len(move.line) > 5 else "")
        move_texts.append(f"Move: {move.move} | Eval: {move.evaluation} | Line: {line_preview}")
    moves_text = "\n".join(move_texts)
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

            Your goal is to explain the position **clearly and concisely** without unnecessary introductions or filler.

            FEN: {fen}

            {summary}

            🧩 **Position Highlights:**  
            {highlight_text}

            Top Moves:
            {moves_text}

            Legal Moves Allowed:
            {legal_moves_text}

            {special_instructions}

            🎯 **Your writing rules:**
            - Start immediately with the best move recommendation (no greetings or intros).
            - Use **short paragraphs** (2–3 sentences each).
            - **Bold important moves** (e.g., **d4**, **Bc4**). Use Standard Algebraic Notation (SAN) only.
            - Use emojis lightly to emphasize key ideas (🎯 tactics, 🔥 attacks, 🏰 castling).
            - Include a Quick Table (| Move | Pros | Cons |) if comparing moves.
            - Focus on 1–2 key positional or tactical ideas.

            ❌ Avoid:
            - No UCI in narrative `b1a2`
            - No "In this intriguing position..."
            - No "You have a wonderful opportunity..."
            - No long-winded openings.
            - No vague generalities. Avoid "Stay vigilant", "look for tactics", "Keep the pressure", "find weaknesses" to exploit", "every move counts!"
            - No robotic listing of moves without ideas.

            🏁 Coach with energy, precision, and clarity.
              """
    return prompt

