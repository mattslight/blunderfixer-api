# worker.py
import io
import os
import time
from datetime import datetime

import chess.engine
import chess.pgn
from sqlmodel import Session, select

from app.db import engine
from app.models import DrillPosition, Game

STOCKFISH = os.getenv("STOCKFISH_PATH", "/opt/homebrew/bin/stockfish")


def get_cp(info):
    s = info["score"].white()
    return float(
        1e4 if s.is_mate() and s.mate() > 0 else -1e4 if s.is_mate() else s.score()
    )


def shallow_drills(pgn: str):
    game = chess.pgn.read_game(io.StringIO(pgn))
    if not game:
        return []
    board = game.board()
    engine = chess.engine.SimpleEngine.popen_uci(STOCKFISH)
    prev = engine.analyse(board, chess.engine.Limit(depth=12))
    prev_cp = get_cp(prev)
    prev_fen, prev_ply = board.fen(), 0
    drills = []
    ply = 1
    for mv in game.mainline_moves():
        board.push(mv)
        info = engine.analyse(board, chess.engine.Limit(depth=12))
        cp = get_cp(info)
        if prev_cp >= 300 and cp <= 50:
            drills.append((prev_fen, prev_ply, prev_cp - cp))
        prev_cp, prev_fen, prev_ply, ply = cp, board.fen(), ply, ply + 1
    engine.close()
    return drills


if __name__ == "__main__":
    while True:
        with Session(engine) as session:
            stmt = select(Game).where(Game.drills_processed == False).limit(1)
            game = session.exec(stmt).first()
            if not game:
                time.sleep(5)
                continue

            for fen, ply, swing in shallow_drills(game.pgn):
                # derive hero from whose turn it was
                from chess import Board

                board = Board(fen)  # position before the collapse move
                side_to_move = "w" if board.turn else "b"
                hero_name = game.white_username if board.turn else game.black_username

                session.add(
                    DrillPosition(
                        game_id=game.id,
                        username=hero_name,
                        hero_side=side_to_move,
                        fen=fen,
                        ply=ply,
                        eval_swing=swing,
                    )
                )
            game.drills_processed = True
            game.drilled_at = datetime.utcnow()
            session.add(game)
            session.commit()
