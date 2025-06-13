#!/usr/bin/env python3
"""
Backfill script for drill themes.

Recompute themes for all DrillPosition rows using
`app.utils.drill_themes.detect_themes`. Any rows where the computed
list differs from the stored value will be updated.

Usage:
    python scripts/backfill_themes.py
"""
import io
import os
import sys
from typing import Optional

import chess.pgn
from dotenv import load_dotenv
from sqlmodel import Session, select, update

# ensure repo root on path
repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, repo_root)

# load environment for DB connection
load_dotenv(os.path.join(repo_root, ".env"))

from app.db import engine
from app.models import DrillPosition, Game
from app.utils.drill_themes import detect_themes


def get_losing_move(dp: DrillPosition, game: Optional[Game]) -> str:
    """Return the SAN of the move played for this DrillPosition."""
    if dp.losing_move:
        return dp.losing_move
    if not game:
        return ""

    pgn_io = io.StringIO(game.pgn)
    g = chess.pgn.read_game(pgn_io)
    node = g
    for _ in range(dp.ply):
        if node.is_end():
            break
        node = node.variation(0)

    board = node.board()
    if not node.is_end():
        mv = node.variation(0).move
        return board.san(mv)
    return ""


def backfill_themes() -> None:
    with Session(engine) as session:
        positions = session.exec(select(DrillPosition)).all()
        print(f"Scanning {len(positions)} DrillPosition(s)…")

        updated = 0
        for dp in positions:
            game: Optional[Game] = session.get(Game, dp.game_id)
            move_san = get_losing_move(dp, game)
            new_themes = detect_themes(dp.fen, move_san)
            if sorted(new_themes) != sorted(dp.themes):
                session.execute(
                    update(DrillPosition)
                    .where(DrillPosition.id == dp.id)
                    .values(themes=new_themes)
                )
                updated += 1
                print(f"✔ DrillPosition {dp.id}: {dp.themes} → {new_themes}")

        session.commit()
        print(f"✅ Updated {updated} row(s).")


if __name__ == "__main__":
    backfill_themes()
