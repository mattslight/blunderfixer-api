# app/worker.py

import argparse
import io
import multiprocessing
import os
import time
from datetime import datetime, timezone

import chess
import chess.pgn
from chess.engine import Limit, SimpleEngine
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, select

from app.db import engine as db_engine
from app.models import DrillPosition, DrillQueue, Game

STOCKFISH = os.getenv("STOCKFISH_PATH", "stockfish")
SWING_THRESHOLD = 150  # flag any single-move swing ≥ 1.50 pawns


def get_cp(info):
    score_obj = info["score"].white()
    if score_obj.is_mate():
        return float(1e4 if score_obj.mate() > 0 else -1e4)
    return float(score_obj.score())


def shallow_drills_for_hero(sf: SimpleEngine, pgn: str, hero_side: str):
    """
    Scan the game and return positions where the *hero* (not the opponent)
    loses ≥ SWING_THRESHOLD centipawns in a single move.

    Returns: List[(fen_before_move, ply_index, delta_cp)]
    """
    game = chess.pgn.read_game(io.StringIO(pgn))
    if not game:
        return []

    drills: list[tuple[str, int, float]] = []
    ply_idx = 0
    node = game

    while not node.is_end():
        mover_side = "w" if node.board().turn else "b"
        if mover_side == hero_side:
            fen_before = node.board().fen()
            cp_before = get_cp(sf.analyse(node.board(), Limit(depth=12)))

            node = node.variation(0)
            cp_after = get_cp(sf.analyse(node.board(), Limit(depth=12)))

            sign = 1 if hero_side == "w" else -1
            delta = sign * (cp_before - cp_after)

            if delta >= SWING_THRESHOLD:
                drills.append((fen_before, ply_idx, delta))
        else:
            node = node.variation(0)

        ply_idx += 1

    return drills


def process_queue_entry(sf: SimpleEngine, queue_id: str) -> str:
    # Load the queue entry
    with Session(db_engine) as session:
        dq = session.get(DrillQueue, queue_id)
        if not dq:
            return queue_id

        game = session.get(Game, dq.game_id)
        if not game:
            return queue_id

        # Determine which side we're analyzing
        hero_side = (
            "w" if dq.hero_username.lower() == game.white_username.lower() else "b"
        )

        # Collect blunder rows
        rows = []
        for fen, ply, swing in shallow_drills_for_hero(sf, game.pgn, hero_side):
            rows.append(
                DrillPosition(
                    game_id=game.id,
                    username=dq.hero_username,
                    fen=fen,
                    ply=ply,
                    eval_swing=swing,
                    created_at=datetime.now(timezone.utc),
                )
            )

        # Batch DB inserts: use ON CONFLICT DO NOTHING to skip duplicates
        if rows:
            from sqlalchemy.dialects.postgresql import insert

            stmt = insert(DrillPosition).values(
                [
                    {
                        "game_id": row.game_id,
                        "username": row.username,
                        "fen": row.fen,
                        "ply": row.ply,
                        "eval_swing": row.eval_swing,
                        "created_at": row.created_at,
                    }
                    for row in rows
                ]
            )
            stmt = stmt.on_conflict_do_nothing(
                index_elements=["game_id", "username", "ply"]
            )
            session.execute(stmt)
            session.commit()

        # Mark the queue entry complete
        dq.drills_processed = True
        dq.drilled_at = datetime.now(timezone.utc)
        session.add(dq)
        session.commit()

    return queue_id


def fetch_next_batch(limit: int) -> list[str]:
    with Session(db_engine) as session:
        stmt = (
            select(DrillQueue.id)
            .where(DrillQueue.drills_processed == False)
            .limit(limit)
        )
        return session.exec(stmt).all()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Drill worker runner")
    parser.add_argument(
        "--once", action="store_true", help="Run one batch and then exit"
    )
    args = parser.parse_args()

    COUNT = 1

    sf = SimpleEngine.popen_uci(STOCKFISH)
    sf.configure({"Threads": COUNT, "Hash": 4})

    try:
        if args.once:
            # Run exactly one batch then exit
            start = time.time()
            queue_ids = fetch_next_batch(COUNT)
            if not queue_ids:
                print("No unprocessed drills for --once run. Exiting.")
            else:
                print(f"Processing {len(queue_ids)} drills (once)…")
                for qid in queue_ids:
                    done = process_queue_entry(sf, qid)
                    print(f"✓ DrillQueue entry {done} done")
            elapsed = time.time() - start
            print(f"Single batch completed in {elapsed:.2f}s")
        else:
            # Continuous loop
            while True:
                queue_ids = fetch_next_batch(COUNT)
                if not queue_ids:
                    print("No unprocessed drills, sleeping for 5s…")
                    time.sleep(5)
                    continue

                print(f"Processing {len(queue_ids)} drills…")
                for qid in queue_ids:
                    done = process_queue_entry(sf, qid)
                    print(f"✓ DrillQueue entry {done} done")
    finally:
        sf.close()
