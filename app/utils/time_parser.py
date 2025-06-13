# app/utils/time_parser.py
import io
import re
from typing import Optional

import chess.pgn

CLK_RE = re.compile(r"\[%clk\s+(\d+):(\d{2}):(\d{2}(?:\.\d+)?)\]")


def _parse_time_control(tc: Optional[str]) -> tuple[Optional[int], int]:
    if not tc:
        return None, 0
    parts = tc.split("+")
    return (int(parts[0]), int(parts[1]) if len(parts) == 2 else 0)


def _clock_from_comment(comment: Optional[str]) -> Optional[float]:
    if not comment:
        return None
    m = CLK_RE.search(comment)
    if not m:
        return None
    h, m_str, s_str = m.groups()
    try:
        total = int(h) * 3600 + int(m_str) * 60 + float(s_str)
        return round(total, 1)
    except ValueError:
        return None


def extract_time_used(
    pgn: str, time_control: Optional[str], ply: int
) -> Optional[float]:
    game = chess.pgn.read_game(io.StringIO(pgn))
    if not game:
        return None

    base, inc = _parse_time_control(time_control)
    last = {
        "w": float(base) if base is not None else None,
        "b": float(base) if base is not None else None,
    }

    node = game
    for i in range(ply + 1):
        if node.is_end():
            return None
        mover = "w" if node.board().turn else "b"
        nxt = node.variation(0)
        rem = _clock_from_comment(nxt.comment)
        if rem is not None and last[mover] is not None:
            spent = max(0.0, last[mover] + inc - rem)
        else:
            spent = None
        if rem is not None:
            last[mover] = rem
        if i == ply:
            return round(spent, 1) if spent is not None else None
        node = nxt

    return None
