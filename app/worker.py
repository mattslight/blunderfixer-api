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
SWING_THRESHOLD = 100  # flag any single-move swing ≥ 1 pawn


# ─── Evaluation Function ────────────────────────────────────────────────────
def get_cp(info):
    """
    Extract centipawn/mate score from Stockfish analysis, normalized to White's POV.
    +ve = good for White, -ve = good for Black.
    """
    score_obj = info["score"]
    mate_score = score_obj.pov(chess.WHITE).mate()
    cp_score = score_obj.pov(chess.WHITE).score()

    if mate_score is not None:
        raw_score = 10000 - abs(mate_score)
        return raw_score if mate_score > 0 else -raw_score
    elif cp_score is not None:
        return cp_score
    else:
        return 0.0  # Fallback in rare cases


# ─── Drill Extraction Logic ─────────────────────────────────────────────────
def shallow_drills_for_hero(sf: SimpleEngine, pgn: str, hero_side: str):
    """
    Scan a game and return drill-worthy positions where the *hero* loses
    ≥ SWING_THRESHOLD centipawns in a single move.

    Returns: List of (fen_before_move, ply_index, eval_swing, initial_eval)
    """
    game = chess.pgn.read_game(io.StringIO(pgn))
    if not game:
        return []

    drills: list[tuple[str, int, float, float]] = []
    ply_idx = 0
    node = game

    while not node.is_end():
        mover_side = "w" if node.board().turn else "b"
        if mover_side == hero_side:
            fen_before = node.board().fen()
            cp_before = get_cp(
                sf.analyse(node.board(), Limit(depth=18))
            )  # Eval before move

            node = node.variation(0)
            cp_after = get_cp(
                sf.analyse(node.board(), Limit(depth=18))
            )  # Eval after move

            # Compute swing from hero's perspective
            sign = 1 if hero_side == "w" else -1
            delta = sign * (cp_before - cp_after)

            if delta >= SWING_THRESHOLD:
                drills.append((fen_before, ply_idx, delta, cp_before))
        else:
            node = node.variation(0)

        ply_idx += 1

    return drills


# ─── Process a Single DrillQueue Entry ──────────────────────────────────────
def process_queue_entry(sf: SimpleEngine, queue_id: str) -> str:
    with Session(db_engine) as session:
        dq = session.get(DrillQueue, queue_id)
        if not dq:
            return queue_id

        game = session.get(Game, dq.game_id)
        if not game:
            return queue_id

        # Determine hero side (white or black)
        hero_side = (
            "w" if dq.hero_username.lower() == game.white_username.lower() else "b"
        )

        rows = []
        # Extract drills from the game
        for fen, ply, swing, initial_eval in shallow_drills_for_hero(
            sf, game.pgn, hero_side
        ):
            board = chess.Board(fen)

            # Count material for phase classification
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

            # Build DrillPosition row with initial_eval
            rows.append(
                DrillPosition(
                    game_id=game.id,
                    username=dq.hero_username,
                    fen=fen,
                    ply=ply,
                    initial_eval=initial_eval,
                    eval_swing=swing,
                    white_minor_count=white_minor_count,
                    black_minor_count=black_minor_count,
                    white_rook_count=white_rook_count,
                    black_rook_count=black_rook_count,
                    white_queen=white_queen,
                    black_queen=black_queen,
                    created_at=datetime.now(timezone.utc),
                )
            )

        # Batch insert with conflict skipping
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
            session.execute(stmt)
            session.commit()

        # Mark queue as processed
        dq.drills_processed = True
        dq.drilled_at = datetime.now(timezone.utc)
        session.add(dq)
        session.commit()

    return queue_id


# ─── Fetch Next Unprocessed Queue Entries ──────────────────────────────────
def fetch_next_batch(limit: int) -> list[str]:
    with Session(db_engine) as session:
        stmt = (
            select(DrillQueue.id)
            .where(DrillQueue.drills_processed == False)
            .limit(limit)
        )
        return session.exec(stmt).all()


# ─── Worker Entry Point ────────────────────────────────────────────────────
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
