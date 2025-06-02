import os
import sys

import chess
import chess.engine
from sqlalchemy import select, update
from sqlalchemy.orm import Session

# Load repo root path
repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, repo_root)

# Load .env
from dotenv import load_dotenv

load_dotenv(os.path.join(repo_root, ".env"))

# Import DB + models AFTER .env
from app.db import engine
from app.models import DrillPosition

STOCKFISH_PATH = os.getenv("STOCKFISH_PATH", "stockfish")


def backfill_initial_eval():
    with Session(engine) as session:
        positions = (
            session.execute(
                select(DrillPosition).where(DrillPosition.initial_eval == None)
            )
            .scalars()
            .all()
        )

        print(f"Found {len(positions)} positions to backfill...")

        with chess.engine.SimpleEngine.popen_uci(STOCKFISH_PATH) as engine_sf:
            for pos in positions:
                board = chess.Board(pos.fen)
                # Get Stockfish evaluation
                info = engine_sf.analyse(board, chess.engine.Limit(depth=18))
                score_obj = info["score"]
                mate_score = score_obj.pov(chess.WHITE).mate()
                cp_score = score_obj.pov(chess.WHITE).score()

                if mate_score is not None:
                    raw_score = 10000 - abs(mate_score)
                    raw_score = raw_score if mate_score > 0 else -raw_score
                elif cp_score is not None:
                    raw_score = cp_score
                else:
                    print(f"Skipping {pos.id}: No eval (rare case)")
                    continue

                normalized_eval = raw_score  # Already normalized for White POV

                print(
                    f"Drill {pos.id} (FEN: {pos.fen}) → initial_eval: {normalized_eval}"
                )

                # Update in DB
                session.execute(
                    update(DrillPosition)
                    .where(DrillPosition.id == pos.id)
                    .values(initial_eval=normalized_eval)
                )
        session.commit()
        print("Backfill complete.")


if __name__ == "__main__":
    backfill_initial_eval()
