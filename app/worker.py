#!/usr/bin/env python3
"""
scripts/drill_worker.py

DrillQueue worker using a single “within‐tolerance” logic for both
winning_moves and has_one_winning_move.

Usage:
    $ python scripts/drill_worker.py [--once]
"""

import argparse
import io
import os
import time
from datetime import datetime, timezone

import chess
import chess.pgn
from chess.engine import Limit, SimpleEngine
from sqlalchemy.dialects.postgresql import insert
from sqlmodel import Session, select

from app.db import engine as db_engine
from app.models import DrillPosition, DrillQueue, Game

# ─── Config ────────────────────────────────────────────────────────────────
STOCKFISH = os.getenv("STOCKFISH_PATH", "stockfish")
SWING_THRESHOLD = 100  # centipawns to flag a “drill” loss
WINNING_MOVE_TOLERANCE = 20  # cp difference from best to count as “still winning”
DEPTH = 18


# ─── Evaluation / CP helper ─────────────────────────────────────────────────
def get_cp(info) -> float:
    """
    Extract centipawn or mate score from Stockfish analysis, normalized to White’s POV.
    +ve = White‐favorable, −ve = Black‐favorable.
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
) -> tuple[bool, list[str]]:
    """
    1) Run Stockfish with multipv=3 at depth=18.
    2) Convert each line’s CP to “hero’s POV” (signed).
    3) winning_moves = all lines where (best_hero_cp - this_line_hero_cp) <= WINNING_MOVE_TOLERANCE.
    4) has_one_winning_move = (len(winning_moves) == 1).
    """
    analysis = sf.analyse(board, Limit(depth=DEPTH), multipv=3)
    if not isinstance(analysis, list):
        analysis = [analysis]

    hero_cp_list: list[float] = []
    for info in analysis:
        raw_cp = get_cp(info)  # White’s POV
        signed_cp = raw_cp if hero_side == "w" else -raw_cp
        hero_cp_list.append(signed_cp)

    if not hero_cp_list:
        return False, []

    best_hero_cp = hero_cp_list[0]
    moves_within: list[str] = []
    for idx, info in enumerate(analysis):
        diff = best_hero_cp - hero_cp_list[idx]
        if diff <= WINNING_MOVE_TOLERANCE:
            pv_move = info.get("pv")[0]
            moves_within.append(board.san(pv_move))
        else:
            break

    only_flag = len(moves_within) == 1
    return only_flag, moves_within


# ─── Drill‐finding logic ────────────────────────────────────────────────────
def shallow_drills_for_hero(sf: SimpleEngine, pgn: str, hero_side: str):
    """
    Scan game PGN and return positions (fen, ply, swing, initial_eval, move_san)
    where hero_side loses ≥ SWING_THRESHOLD in one move.
    """
    game = chess.pgn.read_game(io.StringIO(pgn))
    if not game:
        return []

    drills: list[tuple[str, int, float, float, str]] = []
    ply_idx = 0
    node = game

    while not node.is_end():
        mover_side = "w" if node.board().turn else "b"
        if mover_side == hero_side:
            fen_before = node.board().fen()
            cp_before = get_cp(sf.analyse(node.board(), Limit(depth=18)))

            next_node = node.variation(0)
            move_san = node.board().san(next_node.move)
            node = next_node

            cp_after = get_cp(sf.analyse(node.board(), Limit(depth=18)))
            sign = 1 if hero_side == "w" else -1
            delta = sign * (cp_before - cp_after)

            if delta >= SWING_THRESHOLD:
                drills.append((fen_before, ply_idx, delta, cp_before, move_san))
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
        for fen, ply, swing, initial_eval, played_move in shallow_drills_for_hero(
            sf, game.pgn, hero_side
        ):
            board = chess.Board(fen)

            white_minor_count = len(board.pieces(chess.BISHOP, chess.WHITE)) + len(
                board.pieces(chess.KNIGHT, chess.WHITE)
            )
            black_minor_count = len(board.pieces(chess.BISHOP, chess.BLACK)) + len(
                board.pieces(chess.KNIGHT, chess.BLACK)
            )
            white_rook_count = len(board.pieces(chess.ROOK, chess.WHITE))
            black_rook_count = len(board.pieces(chess.ROOK, chess.BLACK))
            white_queen = bool(board.pieces(chess.QUEEN, chess.WHITE))
            black_queen = bool(board.pieces(chess.QUEEN, chess.BLACK))

            only_move, win_moves = unified_winning_logic(sf, board, hero_side)

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
                    losing_move=played_move,
                    white_minor_count=white_minor_count,
                    black_minor_count=black_minor_count,
                    white_rook_count=white_rook_count,
                    black_rook_count=black_rook_count,
                    white_queen=white_queen,
                    black_queen=black_queen,
                    created_at=datetime.now(timezone.utc),
                )
            )

        if rows:
            stmt = insert(DrillPosition).values(
                [
                    {
                        "game_id": row.game_id,
                        "username": row.username,
                        "fen": row.fen,
                        "ply": row.ply,
                        "initial_eval": row.initial_eval,
                        "eval_swing": row.eval_swing,
                        "has_one_winning_move": row.has_one_winning_move,
                        "winning_moves": row.winning_moves,
                        "losing_move": row.losing_move,
                        "white_minor_count": row.white_minor_count,
                        "black_minor_count": row.black_minor_count,
                        "white_rook_count": row.white_rook_count,
                        "black_rook_count": row.black_rook_count,
                        "white_queen": row.white_queen,
                        "black_queen": row.black_queen,
                        "created_at": row.created_at,
                    }
                    for row in rows
                ]
            )
            stmt = stmt.on_conflict_do_nothing(
                index_elements=["game_id", "username", "ply"]
            )
            session.exec(stmt)
            session.commit()

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
