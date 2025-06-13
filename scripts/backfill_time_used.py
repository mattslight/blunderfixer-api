#!/usr/bin/env python3
"""Backfill `time_used` for DrillPosition rows.

This script parses clock comments in each game's PGN to determine how much
clock time was spent on the losing move. Only rows where `time_used` is NULL
are updated.

Usage:
    python scripts/backfill_time_used.py
"""

import io
import os
import re
import sys
from typing import Optional

import chess.pgn
from dotenv import load_dotenv
from sqlmodel import Session, select, update

repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, repo_root)

load_dotenv(os.path.join(repo_root, ".env"))

from app.db import engine
from app.models import DrillPosition, Game

CLK_RE = re.compile(r"\[%clk\s+([0-9]+:[0-9]{2}:[0-9]{2})\]")


def _tc_to_seconds(tc: Optional[str]) -> Optional[int]:
    if not tc:
        return None
    base = tc.split("+")[0]
    try:
        return int(base)
    except ValueError:
        return None


def _clock_from_comment(comment: Optional[str]) -> Optional[int]:
    if not comment:
        return None
    m = CLK_RE.search(comment)
    if not m:
        return None
    h, m_str, s = m.group(1).split(":")
    return int(h) * 3600 + int(m_str) * 60 + int(s)


def extract_time_used(pgn: str, time_control: Optional[str], ply: int) -> Optional[int]:
    game = chess.pgn.read_game(io.StringIO(pgn))
    if not game:
        return None
    base = _tc_to_seconds(time_control)
    last_clock = {"w": base, "b": base}
    node = game
    for idx in range(ply + 1):
        if node.is_end():
            return None
        mover = "w" if node.board().turn else "b"
        next_node = node.variation(0)
        remaining = _clock_from_comment(next_node.comment)
        spent = None
        if remaining is not None and last_clock[mover] is not None:
            spent = max(0, last_clock[mover] - remaining)
        if remaining is not None:
            last_clock[mover] = remaining
        if idx == ply:
            return spent
        node = next_node
    return None


def backfill_time_used() -> None:
    with Session(engine) as session:
        stmt = select(DrillPosition).where(DrillPosition.time_used.is_(None))
        positions = session.exec(stmt).scalars().all()
        print(f"Found {len(positions)} DrillPosition(s) to backfill…")

        for dp in positions:
            game: Optional[Game] = session.get(Game, dp.game_id)
            if not game:
                print(f"⚠️  Skipping {dp.id}: game {dp.game_id} not found")
                continue

            time_spent = extract_time_used(game.pgn, game.time_control, dp.ply)
            if time_spent is None:
                continue

            session.execute(
                update(DrillPosition)
                .where(DrillPosition.id == dp.id)
                .values(time_used=time_spent)
            )
            print(f"DrillPosition {dp.id}: time_used={time_spent}")

        session.commit()
        print("✅ Backfill complete.")


if __name__ == "__main__":
    backfill_time_used()
