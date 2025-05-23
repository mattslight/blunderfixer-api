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
from app.models import DrillPosition, Game

# Path to your Stockfish binary
STOCKFISH = os.getenv("STOCKFISH_PATH", "/opt/homebrew/bin/stockfish")


def get_cp(info):
    """
    Convert Stockfish score to centipawns, handling mate scores.
    """
    s = info["score"].white()
    if s.is_mate():
        return float(1e4 if s.mate() > 0 else -1e4)
    return float(s.score())


def shallow_drills(pgn: str):
    """
    Perform a depth-12 pass over the PGN, returning collapse candidates.
    Returns a list of (fen_before, ply_index, eval_swing).
    """
    game = chess.pgn.read_game(io.StringIO(pgn))
    if not game:
        return []

    board = game.board()
    eng = chess.engine.SimpleEngine.popen_uci(STOCKFISH)
    # Force single-threaded engine to match one process per core
    try:
        eng.configure({"Threads": 1})
    except Exception:
        pass

    # Initial evaluation before first move
    prev_info = eng.analyse(board, chess.engine.Limit(depth=12))
    prev_cp = get_cp(prev_info)
    prev_fen, prev_ply = board.fen(), 0

    drills = []
    ply = 1
    for mv in game.mainline_moves():
        board.push(mv)
        info = eng.analyse(board, chess.engine.Limit(depth=12))
        cp = get_cp(info)
        # Collapse rule: previous >= +3.0 and now <= +0.5
        if prev_cp >= 300 and cp <= 50:
            drills.append((prev_fen, prev_ply, prev_cp - cp))
        prev_cp, prev_fen, prev_ply, ply = cp, board.fen(), ply, ply + 1

    eng.close()
    return drills


def process_game(game_id: str):
    """
    Process one game: detect drills, store them, mark game processed.
    """
    with Session(engine) as session:
        game = session.get(Game, game_id)
        for fen, ply, swing in shallow_drills(game.pgn):
            board = chess.Board(fen)
            side = "w" if board.turn else "b"
            hero = game.white_username if board.turn else game.black_username

            session.add(
                DrillPosition(
                    game_id=game.id,
                    username=hero,
                    hero_side=side,
                    fen=fen,
                    ply=ply,
                    eval_swing=swing,
                    created_at=datetime.utcnow(),
                )
            )

        game.drills_processed = True
        game.drilled_at = datetime.utcnow()
        session.add(game)
        session.commit()

    return game_id


if __name__ == "__main__":
    # Determine available CPU cores
    cpu_count = multiprocessing.cpu_count()
    print(f"🔧 Worker starting with {cpu_count} cores")

    while True:
        with Session(engine) as session:
            # Fetch up to `cpu_count` unprocessed games
            stmt = (
                select(Game.id).where(Game.drills_processed == False).limit(cpu_count)
            )
            game_ids = [gid for (gid,) in session.exec(stmt).all()]

        if not game_ids:
            print("No unprocessed games, sleeping for 5s…")
            time.sleep(5)
            continue

        print(f"⚙️  Dispatching {len(game_ids)} games over {cpu_count} workers…")
        with ProcessPoolExecutor(max_workers=cpu_count) as pool:
            for finished in pool.map(process_game, game_ids):
                print(f"✓ Game {finished} done")
