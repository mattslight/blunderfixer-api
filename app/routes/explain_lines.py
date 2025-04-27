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
    prompt = build_prompt(req.fen, req.top_moves, req.legal_moves)

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


def build_prompt(fen: str, top_moves: list, legal_moves: list) -> str:
    move_texts = []
    for move in top_moves:
        line_preview = " → ".join(move.line[:5]) + (" ..." if len(move.line) > 5 else "")
        move_texts.append(f"Move: {move.move} | Eval: {move.evaluation} | Line: {line_preview}")

    moves_text = "\n".join(move_texts)

    legal_moves_text = ", ".join(legal_moves) if legal_moves else "No legal moves"

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

            Top Moves:
            {moves_text}

            Legal Moves Allowed:
            {legal_moves_text}

            {special_instructions}

            🎯 **Your writing rules:**
            - Start immediately with the best move recommendation (no greetings or intros).
            - Use **short paragraphs** (2–3 sentences each).
            - **Bold important moves** (e.g., **d4**, **Bc4**).
            - Use emojis lightly to emphasize key ideas (🎯 tactics, 🔥 attacks, 🏰 castling).
            - Include a Quick Table (| Move | Pros | Cons |) if comparing moves.
            - Focus on 1–2 key positional or tactical ideas.

            ❌ Avoid:
            - No "In this intriguing position..."
            - No "You have a wonderful opportunity..."
            - No long-winded openings.
            - No robotic listing of moves without ideas.

            🏁 Coach with energy, precision, and clarity.
              """
    return prompt

