#!/usr/bin/env python
"""
Backfill missing material counts for DrillPosition.
This script loads .env automatically and uses the app's engine.
Usage:
    python scripts/update_drillposition_missing_material.py
"""
import os
import sys

# ensure repo root is on path
repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, repo_root)

# load .env
from dotenv import load_dotenv

load_dotenv(os.path.join(repo_root, ".env"))

import chess
from sqlmodel import Session, select

# import the shared engine and models
from app.db import engine
from app.models import DrillPosition


def compute_counts(fen: str):
    board = chess.Board(fen)
    wm = len(board.pieces(chess.BISHOP, chess.WHITE)) + len(
        board.pieces(chess.KNIGHT, chess.WHITE)
    )
    bm = len(board.pieces(chess.BISHOP, chess.BLACK)) + len(
        board.pieces(chess.KNIGHT, chess.BLACK)
    )
    wr = len(board.pieces(chess.ROOK, chess.WHITE))
    br = len(board.pieces(chess.ROOK, chess.BLACK))
    wq = bool(board.pieces(chess.QUEEN, chess.WHITE))
    bq = bool(board.pieces(chess.QUEEN, chess.BLACK))
    return wm, bm, wr, br, wq, bq


def main():
    with Session(engine) as session:
        stmt = select(DrillPosition).where(
            (DrillPosition.white_minor_count == None)
            | (DrillPosition.black_minor_count == None)
            | (DrillPosition.white_rook_count == None)
            | (DrillPosition.black_rook_count == None)
            | (DrillPosition.white_queen == None)
            | (DrillPosition.black_queen == None)
        )
        results = session.exec(stmt).all()
        print(f"Found {len(results)} records to backfill.")
        for d in results:
            wm, bm, wr, br, wq, bq = compute_counts(d.fen)
            d.white_minor_count = wm
            d.black_minor_count = bm
            d.white_rook_count = wr
            d.black_rook_count = br
            d.white_queen = wq
            d.black_queen = bq
            session.add(d)
        session.commit()
        print("Backfill complete.")


if __name__ == "__main__":
    main()
