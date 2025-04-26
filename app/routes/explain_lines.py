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
    prompt = build_prompt(req.fen, req.top_moves)

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


def build_prompt(fen: str, top_moves: list) -> str:
    move_texts = []
    for move in top_moves:
        line_preview = " → ".join(move.line[:5]) + (" ..." if len(move.line) > 5 else "")
        move_texts.append(f"Move: {move.move} | Eval: {move.evaluation} | Line: {line_preview}")

    moves_text = "\n".join(move_texts)

    prompt = f"""
You are a chess coach for a club-level player (~1400 rating).

Given the following chess FEN and top move suggestions, write a **fun and insightful explanation** for the position.

FEN: {fen}

Top Moves:
{moves_text}

Format and Style Rules:
- Start with a 1-sentence **headline** that captures the key idea (and optionally an emoji 🎯 ♟️ 🔥).
- Bold important squares, pieces, and plans.
- Use short paragraphs (2-4 sentences each).
- Identify 1 tactical motif and 1 strategic plan clearly.
- End with a short 1-line motivational nudge for the player ("Stay sharp!" / "Time to dominate!" / etc.)
- Keep it around 120–150 words.
- Make it engaging and clear — you're coaching, not writing an academic paper.

Do NOT list moves robotically — focus on ideas and energy!
"""
    return prompt
