import os
from typing import Any, Dict, List, Optional, Union

import chess
import chess.engine

ENGINE_PATH = os.getenv("STOCKFISH_PATH", "/usr/bin/stockfish")


def _classify_delta(delta: int, rank: int = 0) -> str:
    if rank == 1 and delta == 0:
        return "⭐️ Top move"
    if delta < 20:
        return "✅ Good move"
    if delta < 50:
        return "⚠️ OK move"
    if delta < 100:
        return "⚠️ Risky move"
    return "❌ Bad move"


def analyze_move_in_stockfish(
    fen: str,
    move_str: str,
    depth: int = 18,
    multipv: int = 1,
    top_lines: Optional[List[Dict[str, Union[List[str], int]]]] = None,
) -> Dict[str, Any]:
    """
    top_lines: optional list of dicts like {'moves': [...], 'scoreCP': int}, ordered by rank.
    """
    result: Dict[str, Any] = {"fen": fen, "input": move_str}

    # 1) parse FEN
    try:
        board = chess.Board(fen)
    except Exception as e:
        result["error"] = f"Invalid FEN: {e}"
        return result

    # 2) determine mover_color
    mover = board.turn

    # 3) find the Move object
    move_obj = None
    try:
        candidate = chess.Move.from_uci(move_str)
        if candidate in board.legal_moves:
            move_obj = candidate
    except Exception:
        pass
    if move_obj is None:
        try:
            move_obj = board.parse_san(move_str)
        except Exception:
            result["error"] = f"Could not interpret move '{move_str}'"
            return result

    # 4) if we have top_lines, try to match
    if top_lines:
        top_score = top_lines[0]["scoreCP"]
        for line in top_lines:
            first = line["moves"][0]
            # allow matching SAN or UCI
            if first.lower() == move_str.lower() or first == move_obj.uci():
                rank = line["rank"]  # ? pull the rank out
                new_score = line["scoreCP"]
                delta = abs(top_score - new_score)
                result.update(
                    {
                        "uci": move_obj.uci(),
                        "score_centipawns": new_score,
                        "delta": delta,
                        "verdict": _classify_delta(delta, rank),
                        "pv": line["moves"],
                    }
                )
                return result

    # 5) otherwise fall back to full Stockfish
    try:
        with chess.engine.SimpleEngine.popen_uci(ENGINE_PATH) as eng:
            # baseline
            base_info = eng.analyse(board, limit=chess.engine.Limit(depth=depth))
            base_cp = base_info["score"].pov(mover).score(mate_score=1_000_000)

            # push & analyse
            board.push(move_obj)
            result["uci"] = move_obj.uci()
            info = eng.analyse(
                board, limit=chess.engine.Limit(depth=depth), multipv=multipv
            )
    except Exception as e:
        result["error"] = f"Engine failure: {e}"
        return result

    # 6) normalize & extract
    if isinstance(info, list):
        info = info[0]
    pov = info["score"].pov(mover)
    new_cp = pov.score(mate_score=1_000_000)
    delta = abs(base_cp - new_cp)
    pv = info.get("pv", [])

    result.update(
        {
            "score_centipawns": new_cp,
            "mate": pov.mate(),
            "delta": delta,
            "verdict": _classify_delta(delta),
            "pv": [m.uci() for m in pv],
        }
    )
    return result
