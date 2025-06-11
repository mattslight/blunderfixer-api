#!/usr/bin/env python3
"""
Backfill missing `winning_lines` and `winning_moves` for DrillPosition rows.
This script mirrors the logic used by the worker so all rows store the engine's
principal variations when a position has a clear advantage for the hero.

Usage:
    python scripts/backfill_winning_lines.py
"""

import io
import os
import sys

import chess
import chess.pgn
from chess.engine import SimpleEngine, Limit
from dotenv import load_dotenv
from sqlalchemy import select, update
from sqlmodel import Session

repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, repo_root)

load_dotenv(os.path.join(repo_root, ".env"))

from app.db import engine as db_engine
from app.models import DrillPosition, Game

STOCKFISH_PATH = os.getenv("STOCKFISH_PATH", "stockfish")
DEPTH = 18
WINNING_MOVE_TOLERANCE = 50


def get_cp(info) -> float:
    score_obj = info["score"]
    mate = score_obj.pov(chess.WHITE).mate()
    cp = score_obj.pov(chess.WHITE).score()
    if mate is not None:
        raw = 10000 - abs(mate)
        return raw if mate > 0 else -raw
    return cp or 0.0


def unified_winning_logic(sf: SimpleEngine, board: chess.Board, hero_side: str) -> tuple[bool, list[str], list[list[str]]]:
    analysis = sf.analyse(board, Limit(depth=DEPTH), multipv=3)
    if not isinstance(analysis, list):
        analysis = [analysis]

    hero_cp: list[float] = []
    lines: list[list[str]] = []
    for info in analysis:
        raw = get_cp(info)
        hero_cp.append(raw if hero_side == "w" else -raw)

        pv: list[str] = []
        copy = board.copy()
        for mv in info.get("pv", []):
            pv.append(copy.san(mv))
            copy.push(mv)
        lines.append(pv)

    if not hero_cp:
        return False, [], []

    best = hero_cp[0]
    moves: list[str] = []
    lines_within: list[list[str]] = []
    for idx, _ in enumerate(analysis):
        diff = best - hero_cp[idx]
        if diff <= WINNING_MOVE_TOLERANCE:
            moves.append(lines[idx][0] if lines[idx] else "")
            lines_within.append(lines[idx])
        else:
            break

    only = len(moves) == 1
    return only, moves, lines_within


def backfill_winning_lines():
    with Session(db_engine) as session:
        stmt = select(DrillPosition).where(DrillPosition.winning_lines.is_(None))
        positions = session.exec(stmt).scalars().all()
        print(f"Found {len(positions)} DrillPosition(s) needing winning_lines…")

        with SimpleEngine.popen_uci(STOCKFISH_PATH) as sf:
            sf.configure({"Threads": 1, "Hash": 16})
            for dp in positions:
                game: Game | None = session.get(Game, dp.game_id)
                if not game:
                    print(f"⚠️  Skipping {dp.id}: game {dp.game_id} not found")
                    continue

                hero = "w" if dp.username.lower() == game.white_username.lower() else "b"

                pgn_io = io.StringIO(game.pgn)
                g = chess.pgn.read_game(pgn_io)
                node = g
                for _ in range(dp.ply):
                    if node.is_end():
                        break
                    node = node.variation(0)

                board = node.board()
                if board.fen() != dp.fen:
                    print(f"⚠️  FEN mismatch for {dp.id}; continuing anyway")

                only, moves, lines = unified_winning_logic(sf, board, hero)
                session.execute(
                    update(DrillPosition)
                    .where(DrillPosition.id == dp.id)
                    .values(
                        has_one_winning_move=only,
                        winning_moves=moves or None,
                        winning_lines=lines or None,
                    )
                )
                print(f"DrillPosition {dp.id}: {len(lines)} lines")

            session.commit()
            print("✅ Backfill complete.")


if __name__ == "__main__":
    backfill_winning_lines()
