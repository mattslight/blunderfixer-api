#!/usr/bin/env python3
"""
scripts/drill_worker.py

DrillQueue worker using a single “within‑tolerance” logic for both
winning_moves and has_one_winning_move, reusing shared time‑parsing logic.

Usage:
    $ python scripts/drill_worker.py [--once]
"""

import argparse
import io
import os
import time
from datetime import datetime, timezone
from typing import Optional

import chess
import chess.pgn
from chess.engine import Limit, SimpleEngine
from sqlalchemy.dialects.postgresql import insert
from sqlmodel import Session, select

from app.db import engine as db_engine
from app.models import DrillPosition, DrillQueue, Game
from app.utils.drill_themes import detect_themes
from app.utils.time_parser import extract_time_used

# ─── Config ────────────────────────────────────────────────────────────────
STOCKFISH = os.getenv("STOCKFISH_PATH", "stockfish")
SWING_THRESHOLD = 100  # centipawns to flag a “drill” loss
WINNING_MOVE_TOLERANCE = 50  # cp difference from best to count as “still winning”
DEPTH = 18  # search depth for Stockfish analysis


# ─── Evaluation / CP helper ─────────────────────────────────────────────────


def get_cp(info) -> float:
    """
    Extract centipawn or mate score from Stockfish analysis, normalized to White’s POV.
    +ve = White‑favorable, −ve = Black‑favorable.
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
    1) Run Stockfish with multipv=3 at configured DEPTH.
    2) Convert each PV line’s CP to hero’s POV (signed).
    3) winning_moves: all lines where (best_hero_cp - this_line_cp) <= WINNING_MOVE_TOLERANCE.
    4) has_one_winning_move: True if exactly one such line.
    """
    analysis = sf.analyse(board, Limit(depth=DEPTH), multipv=3)
    if not isinstance(analysis, list):
        analysis = [analysis]

    hero_cp_list: list[float] = []
    all_lines: list[list[str]] = []
    for info in analysis:
        raw_cp = get_cp(info)
        signed_cp = raw_cp if hero_side == "w" else -raw_cp
        hero_cp_list.append(signed_cp)

        # build the principal variation as SAN moves
        pv_line: list[str] = []
        b_copy = board.copy()
        for mv in info.get("pv", []):
            pv_line.append(b_copy.san(mv))
            b_copy.push(mv)
        all_lines.append(pv_line)

    if not hero_cp_list:
        return False, [], []

    best_hero_cp = hero_cp_list[0]
    moves_within: list[str] = []
    lines_within: list[list[str]] = []
    for idx, _ in enumerate(analysis):
        diff = best_hero_cp - hero_cp_list[idx]
        if diff <= WINNING_MOVE_TOLERANCE:
            moves_within.append(all_lines[idx][0] if all_lines[idx] else "")
            lines_within.append(all_lines[idx])
        else:
            break

    return (len(moves_within) == 1), moves_within, lines_within


# ─── Drill‑finding logic ────────────────────────────────────────────────────


def shallow_drills_for_hero(
    sf: SimpleEngine, pgn: str, hero_side: str, time_control: Optional[str] = None
):
    """
    Scan a game PGN and return tuples of (fen, ply, swing, initial_eval, move_san, time_used)
    for every hero move where the evaluation drop (swing) ≥ SWING_THRESHOLD.
    time_used is parsed via the shared extract_time_used() util.
    """
    game = chess.pgn.read_game(io.StringIO(pgn))
    if not game:
        return []

    drills: list[tuple[str, int, float, float, str, Optional[float]]] = []
    ply_idx = 0
    node = game

    # iterate through all half‑moves
    while not node.is_end():
        mover = "w" if node.board().turn else "b"

        if mover == hero_side:
            fen_before = node.board().fen()
            cp_before = get_cp(sf.analyse(node.board(), Limit(depth=DEPTH)))

            next_node = node.variation(0)
            move_san = node.board().san(next_node.move)
            node = next_node

            cp_after = get_cp(sf.analyse(node.board(), Limit(depth=DEPTH)))
            delta = (cp_before - cp_after) * (1 if hero_side == "w" else -1)

            if delta >= SWING_THRESHOLD:
                # use the same extract_time_used for backfill consistency
                time_used = extract_time_used(pgn, time_control, ply_idx)
                drills.append(
                    (
                        fen_before,
                        ply_idx,
                        delta,
                        cp_before,
                        move_san,
                        time_used,
                    )
                )
        else:
            node = node.variation(0)

        ply_idx += 1

    return drills


# ─── Process a single DrillQueue entry ─────────────────────────────────────


def process_queue_entry(sf: SimpleEngine, queue_id: str) -> str:
    with Session(db_engine) as session:
        dq = session.get(DrillQueue, queue_id)
        if not dq:
            return queue_id

        game = session.get(Game, dq.game_id)
        if not game:
            return queue_id

        hero_side = (
            "w" if dq.hero_username.lower() == game.white_username.lower() else "b"
        )

        rows: list[DrillPosition] = []

        # find all losing swings and prepare DrillPosition entries
        for (
            fen,
            ply,
            swing,
            initial_eval,
            played_move,
            time_used,
        ) in shallow_drills_for_hero(sf, game.pgn, hero_side, game.time_control):
            board = chess.Board(fen)

            # board feature counts
            white_minors = len(board.pieces(chess.BISHOP, chess.WHITE)) + len(
                board.pieces(chess.KNIGHT, chess.WHITE)
            )
            black_minors = len(board.pieces(chess.BISHOP, chess.BLACK)) + len(
                board.pieces(chess.KNIGHT, chess.BLACK)
            )
            white_rooks = len(board.pieces(chess.ROOK, chess.WHITE))
            black_rooks = len(board.pieces(chess.ROOK, chess.BLACK))

            only_move, win_moves, win_lines = unified_winning_logic(
                sf, board, hero_side
            )
            themes = detect_themes(fen, played_move)

            rows.append(
                DrillPosition(
                    game_id=game.id,
                    username=dq.hero_username,
                    fen=fen,
                    ply=ply,
                    initial_eval=initial_eval,
                    eval_swing=swing,
                    has_one_winning_move=only_move,
                    winning_moves=win_moves,
                    winning_lines=win_lines,
                    losing_move=played_move,
                    time_used=time_used,
                    themes=themes,
                    white_minor_count=white_minors,
                    black_minor_count=black_minors,
                    white_rook_count=white_rooks,
                    black_rook_count=black_rooks,
                    white_queen=bool(board.pieces(chess.QUEEN, chess.WHITE)),
                    black_queen=bool(board.pieces(chess.QUEEN, chess.BLACK)),
                    created_at=datetime.now(timezone.utc),
                )
            )

        # bulk insert, ignoring duplicates
        if rows:
            stmt = insert(DrillPosition).values(
                [row.dict(exclude_unset=True) for row in rows]
            )
            stmt = stmt.on_conflict_do_nothing(
                index_elements=["game_id", "username", "ply"]
            )
            session.exec(stmt)
            session.commit()

        # mark queue entry done
        dq.drills_processed = True
        dq.drilled_at = datetime.now(timezone.utc)
        session.add(dq)
        session.commit()

    return queue_id


# ─── Fetch next batch of unprocessed DrillQueue IDs ────────────────────────


def fetch_next_batch(limit: int) -> list[str]:
    with Session(db_engine) as session:
        stmt = (
            select(DrillQueue.id)
            .where(DrillQueue.drills_processed == False)
            .limit(limit)
        )
        return session.exec(stmt).all()


# ─── Worker entry point ─────────────────────────────────────────────────────
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Drill worker runner")
    parser.add_argument(
        "--once", action="store_true", help="Run through all batches once, then exit"
    )
    args = parser.parse_args()

    COUNT = 1
    sf = SimpleEngine.popen_uci(STOCKFISH)
    sf.configure({"Threads": COUNT, "Hash": 4})

    try:
        start = time.time()
        while True:
            queue_ids = fetch_next_batch(COUNT)
            if not queue_ids:
                if args.once:
                    break
                print("No unprocessed drills, sleeping for 5s…")
                time.sleep(5)
                continue

            print(f"Processing {len(queue_ids)} drills…")
            for qid in queue_ids:
                done = process_queue_entry(sf, qid)
                print(f"✓ DrillQueue entry {done} done")

            if args.once:
                continue

        if args.once:
            elapsed = time.time() - start
            print(f"All batches completed in {elapsed:.2f}s")
        else:
            print("Worker exiting")
    finally:
        sf.close()
