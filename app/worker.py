# app/worker.py

import io
import multiprocessing
import os
import time
from concurrent.futures import ProcessPoolExecutor
from datetime import datetime, timezone

import chess
import chess.engine
import chess.pgn
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, select

from app.db import engine as db_engine
from app.models import DrillPosition, DrillQueue, Game

STOCKFISH = os.getenv("STOCKFISH_PATH", "stockfish")
SWING_THRESHOLD = 150  # flag any single‐move swing ≥ 1.50 pawns


def get_cp(info):
    score_obj = info["score"].white()
    if score_obj.is_mate():
        return float(1e4 if score_obj.mate() > 0 else -1e4)
    return float(score_obj.score())


def shallow_drills_for_hero(pgn: str, hero_side: str):
    """
    Scan the game and return positions where the *hero* (not the opponent)
    loses ≥ SWING_THRESHOLD centipawns in a single move.

    Returns: List[(fen_before_move, ply_index, delta_cp)]
    """
    game = chess.pgn.read_game(io.StringIO(pgn))
    if not game:
        return []

    sf = chess.engine.SimpleEngine.popen_uci(STOCKFISH)
    try:
        sf.configure({"Threads": 1, "Hash": 4})
    except Exception:
        pass

    drills: list[tuple[str, int, float]] = []
    ply_idx = 0  # half-move counter from the start position

    node = game
    while not node.is_end():
        mover_side = "w" if node.board().turn else "b"

        # analyse only the hero's own moves
        if mover_side == hero_side:
            fen_before = node.board().fen()
            cp_before = get_cp(sf.analyse(node.board(), chess.engine.Limit(depth=12)))

            # position *after* hero’s move
            node = node.variation(0)
            cp_after = get_cp(sf.analyse(node.board(), chess.engine.Limit(depth=12)))

            # compute delta from the hero's POV:
            #  - if hero is White, delta = white_cp_before - white_cp_after
            #  - if hero is Black, delta = black_cp_before - black_cp_after
            #    but black_cp = -white_cp, so we invert the sign:
            sign = 1 if hero_side == "w" else -1
            delta = sign * (cp_before - cp_after)

            if delta >= SWING_THRESHOLD:
                drills.append((fen_before, ply_idx, delta))
        else:
            node = node.variation(0)  # just advance (opponent move)

        ply_idx += 1

    sf.close()
    return drills


def process_queue_entry(queue_id: str):
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

        # --- Phase 1: insert drills one at a time ---
        for fen, ply, swing in shallow_drills_for_hero(game.pgn, hero_side):
            dp = DrillPosition(
                game_id=game.id,
                username=dq.hero_username,
                fen=fen,
                ply=ply,
                eval_swing=swing,
                created_at=datetime.now(timezone.utc),
            )
            session.add(dp)
            try:
                session.commit()
            except IntegrityError:
                session.rollback()  # skip duplicates

        # --- Phase 2: mark the queue complete ---
        dq.drills_processed = True
        dq.drilled_at = datetime.now(timezone.utc)
        session.add(dq)
        session.commit()

    return queue_id


if __name__ == "__main__":

    COUNT = 4

    print(f"🔧 Worker starting with {COUNT} sessions")

    while True:
        with Session(db_engine) as session:
            stmt = (
                select(DrillQueue.id)
                .where(DrillQueue.drills_processed == False)
                .limit(COUNT)
            )
            queue_ids = session.exec(stmt).all()

        if not queue_ids:
            print("No unprocessed drills, sleeping for 5s…")
            time.sleep(5)
            continue

        print(f"⚙️  Dispatching {len(queue_ids)} drills over {COUNT} workers…")
        with ProcessPoolExecutor(max_workers=COUNT) as pool:
            for done_id in pool.map(process_queue_entry, queue_ids):
                print(f"✓ DrillQueue entry {done_id} done")
