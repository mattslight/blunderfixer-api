from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
import chess.pgn
import io


from app.utils.phase_detector import get_game_phase

router = APIRouter()

class PhaseRequest(BaseModel):
    pgn: str

class PhaseResponseItem(BaseModel):
    move_number: int
    san: str
    phase: str

def clean_pgn(pgn_text: str) -> str:
    import re

    # Remove all {...} comments
    pgn_text = re.sub(r'\{.*?\}', '', pgn_text)

    # Remove Chess.com clock info and other tags
    pgn_text = re.sub(r'\[%.*?\]', '', pgn_text)
    pgn_text = re.sub(r'\[CurrentPosition .*?\]', '', pgn_text)

    # Replace "1... c6" with just "c6" (removes extra black move labels)
    pgn_text = re.sub(r'\d+\.\.\.\s*', '', pgn_text)

    # Strip repeated white move numbers (e.g. "1. e4 1... c6" → "1. e4 c6")
    pgn_text = re.sub(r'(\d+)\.\s+', r'\1. ', pgn_text)

    print("--- CLEANED PGN ---")
    print(pgn_text)

    return pgn_text.strip()

@router.post("/phase", response_model=list[PhaseResponseItem])
def evaluate_phase(request: PhaseRequest):
    try:
        pgn = clean_pgn(request.pgn)
        pgn_io = io.StringIO(pgn)
        game = chess.pgn.read_game(pgn_io)

        if game is None:
            raise HTTPException(status_code=400, detail="Invalid PGN provided.")

        evaluations = []
        board = game.board()

        move_number = 0
        for move in game.mainline_moves():
            move_number += 1

            # Get SAN before push
            san = board.san(move)

            # Push the move
            board.push(move)

            # Create fake move stack if needed for phase detector
            move_stack = []  # <-- you probably need this if get_game_phase expects a move stack
            phase = get_game_phase(board, board.fullmove_number, move_stack)

            evaluations.append(PhaseResponseItem(
                move_number=move_number,
                san=san,
                phase=phase
            ))

        return evaluations



    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
