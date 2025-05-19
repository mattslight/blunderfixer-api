import os
from typing import Any, Dict, Optional

import chess
import chess.engine

ENGINE_PATH = os.getenv("STOCKFISH_PATH", "/usr/bin/stockfish")


def analyze_move_in_stockfish(
    fen: str,
    move_str: str,
    depth: int = 20,
    multipv: int = 1,
) -> Dict[str, Any]:
    """
    Safely apply a move (UCI or SAN) on `fen`, run Stockfish to `depth` with `multipv`,
    and return a structured result including eval, mate, and principal variation.
    Error conditions produce an 'error' key instead of raising.
    """
    result: Dict[str, Any] = {"fen": fen, "input": move_str}

    # 1) Parse the FEN
    try:
        board = chess.Board(fen)
    except Exception as e:
        result["error"] = f"Invalid FEN: {e}"
        return result

    # 2) Determine mover_color (always the side to move before push)
    mover_color = board.turn

    # 3) Try UCI first
    move_obj: Optional[chess.Move] = None
    try:
        candidate = chess.Move.from_uci(move_str)
        if candidate in board.legal_moves:
            move_obj = candidate
    except Exception:
        pass

    # 4) Fallback to SAN
    if move_obj is None:
        try:
            move_obj = board.parse_san(move_str)
        except Exception:
            result["error"] = f"Could not interpret move '{move_str}'"
            return result

    # 5) Open engine once, get baseline & post?move eval
    try:
        with chess.engine.SimpleEngine.popen_uci(ENGINE_PATH) as eng:
            # 5a) Baseline eval BEFORE the move
            baseline = eng.analyse(board, limit=chess.engine.Limit(depth=depth))
            eval0 = baseline["score"].pov(board.turn).score(mate_score=1_000_000)

            # 5b) Push the move and record its UCI
            board.push(move_obj)
            result["uci"] = move_obj.uci()

            # 5c) Analysis AFTER the move
            info = eng.analyse(
                board,
                limit=chess.engine.Limit(depth=depth),
                multipv=multipv,
            )
    except Exception as e:
        result["error"] = f"Engine failure: {e}"
        return result

    # 7) Normalize multipv output (list → single dict)
    if isinstance(info, list):
        info = info[0]

    # 8) Extract evaluation and mate distance
    score = info.get("score")
    if score is not None:
        pov = score.pov(mover_color)
        result["score_centipawns"] = pov.score(mate_score=1_000_000)
        result["mate"] = pov.mate()
        # 8a) Compute delta vs. baseline
        result["delta"] = result["score_centipawns"] - eval0

    # 9) Extract principal variation
    pv = info.get("pv") or []
    result["pv"] = [m.uci() for m in pv]

    return result
