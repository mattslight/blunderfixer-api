import openai
from fastapi import APIRouter
from pydantic import BaseModel
import os
from dotenv import load_dotenv

load_dotenv()

router = APIRouter()

openai_api_key = os.getenv("OPENAI_API_KEY")
client = openai.OpenAI(api_key=openai_api_key)

class CoachChatRequest(BaseModel):
    fen: str
    past_messages: list
    user_message: str
    legal_moves: list

def build_coach_chat_prompt(fen: str, legal_moves: list) -> str:
    legal_moves_str = ", ".join(legal_moves) if legal_moves else "No legal moves"

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

    return f"""
            You are a professional chess coach assisting club-level players (rating 800–1800).

            🧠 Focus on:
            - Practical, actionable advice
            - Short replies (2–4 sentences)
            - Bold key moves (e.g., **d4**, **Bc4**)
            - Use light emojis 🎯🔥🏆 to highlight ideas
            - If asked about a move (e.g., "Is b4 good?"), start with a Quick Verdict:
                - ✅ "Good idea because..."
                - ⚠️ "Risky move because..."

            🎯 Current Position (FEN):
            {fen}

            ✅ Only Legal Moves in this position: {legal_moves_str}

            {special_instructions}

            Coach like you're explaining to a serious student who wants to improve — not memorize theory!
            """

@router.post("/coach-chat", summary="Continue Coach Chat")
def coach_chat(req: CoachChatRequest):
    try:
        system_prompt = build_coach_chat_prompt(req.fen, req.legal_moves)

        messages = [{"role": "system", "content": system_prompt}] + req.past_messages + [
            {"role": "user", "content": req.user_message}
        ]

        response = client.chat.completions.create(
            model="gpt-4o",
            messages=messages,
            temperature=0.7,
            max_tokens=500
        )

        reply = response.choices[0].message.content.strip()

        return {"reply": reply}
    except Exception as e:
        return {"error": str(e)}
