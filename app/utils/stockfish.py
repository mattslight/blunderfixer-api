# app/utils/stockfish.py

import os
from typing import Any, Dict

import chess
import chess.engine

ENGINE_PATH = os.getenv("STOCKFISH_PATH", "/usr/bin/stockfish")
engine = chess.engine.SimpleEngine.popen_uci(ENGINE_PATH)


def analyze_move_in_stockfish(
    fen: str,
    uci: str,
    depth: int = 20,
) -> Dict[str, Any]:
    """
    Push `uci` on `fen`, run a single‐PV Stockfish search to `depth`,
    and return the centipawn score & mate info for that move.
    """
    board = chess.Board(fen)
    mover = board.turn
    board.push_uci(uci)

    info = engine.analyse(
        board,
        limit=chess.engine.Limit(depth=depth),
        # no multipv parameter → single best line only
    )

    pov = info["score"].pov(mover)
    return {
        "uci": uci,
        "score_centipawns": pov.score(mate_score=1_000_000),
        "mate": pov.mate(),
    }
