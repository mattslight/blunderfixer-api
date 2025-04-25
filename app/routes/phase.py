from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
import chess.pgn
import io

from app.utils.phase_detector import get_game_phase
from app.utils.clean_pgn import clean_pgn

router = APIRouter()

class PhaseRequest(BaseModel):
    pgn: str

class PhaseResponseItem(BaseModel):
    move_number: int
    san: str
    phase: str

@router.post("/phase",
             response_model=list[PhaseResponseItem],
             summary="Evaluate Phase",
             description="""
                        Parses a PGN and returns a list of moves, each tagged with its game phase (opening, middlegame, endgame).

                        - Cleans non-standard Chess.com PGNs automatically
                        - Uses deterministic rules based on material and move number
                        """)

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
