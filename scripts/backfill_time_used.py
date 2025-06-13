#!/usr/bin/env python3
"""
scripts/backfill_time_used.py

Backfill script for `time_used` on DrillPosition rows.
Reuses the shared time-parser util to ensure consistency with drill worker.

Usage:
    $ python scripts/backfill_time_used.py
"""

import csv
import io
import os
import sys
from typing import Optional

import chess.pgn
from dotenv import load_dotenv
from sqlmodel import Session, select, update

# ensure the repo root is on PYTHONPATH for imports
repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, repo_root)

load_dotenv(os.path.join(repo_root, ".env"))

from app.db import engine
from app.models import DrillPosition, Game
from app.utils.time_parser import extract_time_used


def backfill_time_used() -> None:
    """
    Find all DrillPosition rows with NULL time_used,
    compute with extract_time_used(), and update.
    """
    skipped = []

    with Session(engine) as session:
        stmt = select(DrillPosition).where(DrillPosition.time_used.is_(None))
        positions = session.exec(stmt).all()
        print(f"Found {len(positions)} DrillPosition(s) to backfill…")

        for dp in positions:
            game: Optional[Game] = session.get(Game, dp.game_id)
            if not game:
                reason = "game not found"
                print(f"⚠️ Skipping {dp.id}: {reason}")
                skipped.append((dp.id, dp.game_id, dp.ply, reason))
                continue

            # use shared util for consistency & correct rounding
            time_spent = extract_time_used(game.pgn, game.time_control, dp.ply)
            if time_spent is None:
                reason = "Unable to parse time"
                print(f"⏭ Skipping {dp.id} – {reason}")
                skipped.append((dp.id, dp.game_id, dp.ply, reason))
                continue

            # update the row
            session.execute(
                update(DrillPosition)
                .where(DrillPosition.id == dp.id)
                .values(time_used=time_spent)
            )
            print(f"✅ DrillPosition {dp.id}: time_used={time_spent}")

        session.commit()
        print("🏁 Backfill complete.")

    if skipped:
        with open("skipped_time_used.csv", "w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(["drill_id", "game_id", "ply", "reason"])
            writer.writerows(skipped)
        print(f"📝 Saved {len(skipped)} skipped rows to skipped_time_used.csv")


if __name__ == "__main__":
    backfill_time_used()
