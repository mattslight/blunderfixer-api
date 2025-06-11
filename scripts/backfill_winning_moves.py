#!/usr/bin/env python3
"""
scripts/backfill_winning_moves.py

Scan all existing DrillPosition rows where any of the new fields
(`losing_move`, `has_one_winning_move`, `winning_moves`, `winning_lines`) are NULL,
then recompute & write them using a single, consistent “within‐tolerance”
logic instead of two separate thresholds.

Usage:
    $ python scripts/backfill_winning_moves.py
"""

import io
import os
import sys
from datetime import datetime, timezone

import chess
import chess.pgn
from chess.engine import Limit, SimpleEngine
from dotenv import load_dotenv
from sqlalchemy import select, update
from sqlmodel import Session  # ← use SQLModel’s Session, not plain SQLAlchemy’s

# ─── Ensure project root is on PYTHONPATH ────────────────────────────────────
repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, repo_root)

# ─── Load environment (e.g. DATABASE_URL, STOCKFISH_PATH) ───────────────────
load_dotenv(os.path.join(repo_root, ".env"))

# ─── Import DB engine & models AFTER loading .env ─────────────────────────
from app.db import engine as db_engine
from app.models import DrillPosition, Game

# ─── Config ────────────────────────────────────────────────────────────────
STOCKFISH_PATH = os.getenv("STOCKFISH_PATH", "stockfish")
SWING_DEPTH = 18  # depth used by the worker
WINNING_MOVE_TOLERANCE = 50  # CP tolerance to include a move as “winning”


# ─── Utility functions copied (and simplified) from app/worker.py ──────────
def get_cp(info) -> float:
    """
    Extract centipawn or mate score from Stockfish analysis, normalized to
    White’s POV. +ve => White‐favorable, −ve => Black‐favorable.
    """
    score_obj = info["score"]
    mate_score = score_obj.pov(chess.WHITE).mate()
    cp_score = score_obj.pov(chess.WHITE).score()

    if mate_score is not None:
        raw = 10000 - abs(mate_score)
        return raw if mate_score > 0 else -raw
    elif cp_score is not None:
        return cp_score
    else:
        return 0.0


def unified_winning_logic(
    sf: SimpleEngine, board: chess.Board, hero_side: str
) -> tuple[bool, list[str], list[list[str]]]:
    """
    1) Query Stockfish for its top 3 lines (multipv=3).
    2) Convert each line’s CP to “hero’s POV” (signed).
    3) winning_moves = all lines whose (best_hero_cp – this_line_hero_cp) <= WINNING_MOVE_TOLERANCE.
    4) has_one_winning_move = (len(winning_moves) == 1).
    """
    analysis = sf.analyse(board, Limit(depth=SWING_DEPTH), multipv=3)
    if not isinstance(analysis, list):
        analysis = [analysis]

    hero_cp_list: list[float] = []
    all_lines: list[list[str]] = []
    for info in analysis:
        raw_cp = get_cp(info)  # White’s POV
        signed_cp = raw_cp if hero_side == "w" else -raw_cp
        hero_cp_list.append(signed_cp)

        pv_line: list[str] = []
        b_copy = board.copy()
        for mv in info.get("pv", []):
            pv_line.append(b_copy.san(mv))
            b_copy.push(mv)
        all_lines.append(pv_line)

    if not hero_cp_list:
        return False, [], []

    best_hero_cp = hero_cp_list[0]

    moves_within_tolerance: list[str] = []
    lines_within: list[list[str]] = []
    for idx, info in enumerate(analysis):
        diff = best_hero_cp - hero_cp_list[idx]
        if diff <= WINNING_MOVE_TOLERANCE:
            moves_within_tolerance.append(all_lines[idx][0] if all_lines[idx] else "")
            lines_within.append(all_lines[idx])
        else:
            break

    only_flag = len(moves_within_tolerance) == 1
    return only_flag, moves_within_tolerance, lines_within


# ─── Main backfill routine ──────────────────────────────────────────────────
def backfill_winning_fields():
    with Session(db_engine) as session:
        # 1) Fetch all DrillPosition rows where any of the new fields is NULL
        stmt = select(DrillPosition).where(
            (DrillPosition.losing_move.is_(None))
            | (DrillPosition.has_one_winning_move.is_(None))
            | (DrillPosition.winning_moves.is_(None))
            | (DrillPosition.winning_lines.is_(None))
        )
        positions = session.exec(stmt).scalars().all()

        print(f"Found {len(positions)} DrillPosition(s) needing backfill…")

        # 2) Launch a single Stockfish instance
        with SimpleEngine.popen_uci(STOCKFISH_PATH) as sf:
            sf.configure({"Threads": 1, "Hash": 16})

            for dp in positions:
                # 3) Load the parent Game to replay up to dp.ply
                game: Game = session.get(Game, dp.game_id)
                if not game:
                    print(f"→ Skipping DP {dp.id}: game_id {dp.game_id} not found")
                    continue

                hero_side = (
                    "w" if dp.username.lower() == game.white_username.lower() else "b"
                )

                # 4) Rewind the PGN to exactly dp.ply half‐moves:
                pgn_io = io.StringIO(game.pgn)
                parsed = chess.pgn.read_game(pgn_io)
                node = parsed
                for _ in range(dp.ply):
                    if node.is_end():
                        break
                    node = node.variation(0)

                board = node.board()
                # If FEN doesn’t match, warn but continue:
                if board.fen() != dp.fen:
                    print(
                        f"⚠️  Warning: ply mismatch for DrillPosition {dp.id}\n"
                        f"   expected FEN: {dp.fen}\n"
                        f"   actual FEN:   {board.fen()}\n"
                        "   continuing anyway…"
                    )

                # 5) Compute losing_move SAN (the move actually played from dp.fen)
                losing_move_san: str | None = None
                if not node.is_end():
                    next_move = node.variation(0).move
                    losing_move_san = board.san(next_move)

                # 6) Compute both fields with a single call:
                only_flag, win_list, line_list = unified_winning_logic(sf, board, hero_side)

                # 7) UPDATE the DrillPosition in one SQL statement:
                session.execute(
                    update(DrillPosition)
                    .where(DrillPosition.id == dp.id)
                    .values(
                        has_one_winning_move=only_flag,
                        winning_moves=win_list or None,
                        winning_lines=line_list or None,
                        losing_move=losing_move_san,
                    )
                )
                print(
                    f"✔ DrillPosition {dp.id}: "
                    f"has_one_winning_move={only_flag}, "
                    f"losing_move={losing_move_san!r}, "
                    f"winning_moves={win_list}"
                    f", winning_lines={line_list}"
                )

            session.commit()
            print("✅ Backfill complete.")


if __name__ == "__main__":
    backfill_winning_fields()
