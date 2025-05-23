# app/worker.py

import io
import multiprocessing
import os
import time
from concurrent.futures import ProcessPoolExecutor
from datetime import datetime

import chess
import chess.engine
import chess.pgn
from sqlmodel import Session, select

from app.db import engine
from app.models import DrillPosition, DrillQueue, Game

STOCKFISH = os.getenv("STOCKFISH_PATH", "stockfish")
SWING_THRESHOLD = 200  # flag any single‐move swing ≥ 2.00 pawns


def get_cp(info):
    score_obj = info["score"].white()
    if score_obj.is_mate():
        return float(1e4 if score_obj.mate() > 0 else -1e4)
    return float(score_obj.score())


SWING_THRESHOLD = 200  # ≥2-pawn loss counts as a drill


def shallow_drills_for_hero(pgn: str, hero_side: str):
    """
    Scan the game and return positions where the *hero* (not the opponent)
    loses ≥ SWING_THRESHOLD centipawns in a single move.

    Returns: List[(fen_before_move, ply_index, delta_cp)]
    """
    game = chess.pgn.read_game(io.StringIO(pgn))
    if not game:
        return []

    engine = chess.engine.SimpleEngine.popen_uci(STOCKFISH)
    try:
        engine.configure({"Threads": 1})
    except Exception:
        pass

    drills: list[tuple[str, int, float]] = []
    ply_idx = 0  # half-move counter from the start position

    node = game
    while not node.is_end():
        move = node.variation(0).move  # next move in main line
        mover_side = "w" if node.board().turn else "b"

        # analyse only the hero's own moves
        if mover_side == hero_side:
            fen_before = node.board().fen()
            cp_before = get_cp(
                engine.analyse(node.board(), chess.engine.Limit(depth=12))
            )

            # position *after* hero’s move
            node = node.variation(0)
            cp_after = get_cp(
                engine.analyse(node.board(), chess.engine.Limit(depth=12))
            )

            delta = cp_before - cp_after
            if delta >= SWING_THRESHOLD:
                drills.append((fen_before, ply_idx, delta))
        else:
            node = node.variation(0)  # just advance (opponent move)

        ply_idx += 1

    engine.close()
    return drills


def process_queue_entry(queue_id: str):
    with Session(engine) as session:
        dq = session.get(DrillQueue, queue_id)
        if not dq:
            return queue_id

        game = session.get(Game, dq.game_id)
        if not game:
            return queue_id

        hero_side = (
            "w" if dq.hero_username.lower() == game.white_username.lower() else "b"
        )

        for fen, ply, swing in shallow_drills_for_hero(game.pgn, hero_side):
            session.add(
                DrillPosition(
                    game_id=game.id,
                    username=dq.hero_username,
                    fen=fen,
                    ply=ply,
                    eval_swing=swing,
                    created_at=datetime.utcnow(),
                )
            )

        dq.drills_processed = True
        dq.drilled_at = datetime.utcnow()
        session.add(dq)
        session.commit()

    return queue_id


if __name__ == "__main__":
    cpu_count = multiprocessing.cpu_count()
    print(f"🔧 Worker starting with {cpu_count} cores")

    while True:
        with Session(engine) as session:
            stmt = (
                select(DrillQueue.id)
                .where(DrillQueue.drills_processed == False)
                .limit(cpu_count)
            )
            queue_ids = session.exec(stmt).all()

        if not queue_ids:
            print("No unprocessed drills, sleeping for 5s…")
            time.sleep(5)
            continue

        print(f"⚙️  Dispatching {len(queue_ids)} drills over {cpu_count} workers…")
        with ProcessPoolExecutor(max_workers=cpu_count) as pool:
            for done_id in pool.map(process_queue_entry, queue_ids):
                print(f"✓ DrillQueue entry {done_id} done")
