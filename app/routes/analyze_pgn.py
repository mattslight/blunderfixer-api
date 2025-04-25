from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
import chess.pgn
import chess.engine
import io

from app.utils.clean_pgn import clean_pgn
from app.utils.phase_detector import get_game_phase

router = APIRouter()

STOCKFISH_PATH = "/opt/homebrew/bin/stockfish"  # Hardcoded for local dev

class TopMove(BaseModel):
    san: str
    eval: float

class AnalyzePGNRequest(BaseModel):
    pgn: str

class AnalyzePGNResponseItem(BaseModel):
    move_number: int
    san: str
    phase: str
    evaluation: float  # eval *after* move is played
    centipawn_loss: float  # eval diff from best move before
    mate: bool
    top_moves: list[TopMove]

@router.post(
    "/analyze-pgn",
    response_model=list[AnalyzePGNResponseItem],
    summary="Analyze Full PGN with Top Engine Moves",
    description="""
Parses a PGN, evaluates each move with Stockfish, and returns evaluations
including the top N engine-recommended moves at each position.
"""
)
def analyze_pgn(request: AnalyzePGNRequest, top_n: int = Query(3, ge=1, le=5)):
    try:
        cleaned = clean_pgn(request.pgn)
        pgn_io = io.StringIO(cleaned)
        game = chess.pgn.read_game(pgn_io)

        if game is None:
            raise HTTPException(status_code=400, detail="Invalid PGN provided.")

        evaluations = []
        board = game.board()
        move_stack = []
        move_number = 0

        with chess.engine.SimpleEngine.popen_uci(STOCKFISH_PATH) as engine:
            for move in game.mainline_moves():
                move_number += 1

                pre_move_board = board.copy()  # BEFORE the move

                # Eval BEFORE move to get top move and compute centipawn loss
                try:
                    info_list = engine.analyse(pre_move_board, chess.engine.Limit(depth=12), multipv=top_n)
                except Exception:
                    raise HTTPException(status_code=500, detail=f"Engine failed on move {move_number} (pre-analysis)")

                if not isinstance(info_list, list):
                    info_list = [info_list]

                top_moves = []
                best_score_before = info_list[0]["score"].white()
                if best_score_before.is_mate():
                    best_eval = 10000.0 if best_score_before.mate() > 0 else -10000.0
                else:
                    best_eval = best_score_before.score() / 100.0

                for info in info_list:
                    best_move = info["pv"][0]
                    score = info["score"].white()
                    if score.is_mate():
                        eval_score = 10000.0 if score.mate() > 0 else -10000.0
                    else:
                        eval_score = score.score() / 100.0

                    top_moves.append(TopMove(
                        san=pre_move_board.san(best_move),
                        eval=round(eval_score, 2)
                    ))

                # Play move
                san = board.san(move)
                board.push(move)
                move_stack.append(move)
                phase = get_game_phase(board, board.fullmove_number, move_stack)

                # Eval AFTER move
                post_score = engine.analyse(board, chess.engine.Limit(depth=12))["score"].white()
                mate = post_score.is_mate()
                if mate:
                    evaluation = 10000.0 if post_score.mate() > 0 else -10000.0
                else:
                    evaluation = post_score.score() / 100.0

                # Determine centipawn loss relative to best move only
                if mate:
                    centipawn_loss = 0.0
                else:
                    if pre_move_board.turn == chess.WHITE:
                        centipawn_loss = round(best_eval - evaluation, 2)
                    else:
                        centipawn_loss = round(evaluation - best_eval, 2)
                    centipawn_loss = max(0.0, centipawn_loss)

                evaluations.append(AnalyzePGNResponseItem(
                    move_number=move_number,
                    san=san,
                    phase=phase,
                    evaluation=round(evaluation, 2),
                    centipawn_loss=centipawn_loss,
                    mate=mate,
                    top_moves=top_moves
                ))

        return evaluations

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))