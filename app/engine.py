import os
import chess
import chess.engine
from dotenv import load_dotenv

# Load environment variables from .env (local dev) or system (Render)
load_dotenv()

# Get STOCKFISH_PATH from environment
STOCKFISH_PATH = os.getenv("STOCKFISH_PATH", "./bin/stockfish")  # default fallback

# Debug print (optional: can delete later)
print(f"✅ Using STOCKFISH_PATH: {STOCKFISH_PATH}")

def analyse_fen(fen: str, depth: int = 15, top_n: int = 1) -> dict:
    board = chess.Board(fen)
    moves = []

    with chess.engine.SimpleEngine.popen_uci(STOCKFISH_PATH) as engine:
        try:
            result = engine.analyse(board, chess.engine.Limit(depth=depth), multipv=top_n)
        except Exception as e:
            return {"error": f"Stockfish failed: {str(e)}"}

        # Ensure result is always a list
        if not isinstance(result, list):
            result = [result]

        for entry in result:
            if "pv" not in entry or not entry["pv"]:
                continue  # Skip incomplete lines

            move = entry["pv"][0].uci()
            score_obj = entry["score"].white()

            if score_obj.is_mate():
                evaluation = f"#{score_obj.mate()}"
            else:
                evaluation = round(score_obj.score() / 100, 2)

            # Extract full best line in SAN
            best_line = []
            temp_board = board.copy()
            for move_obj in entry["pv"]:
                san = temp_board.san(move_obj)
                best_line.append(san)
                temp_board.push(move_obj)

            moves.append({
                "move": move,
                "evaluation": evaluation,
                "line": best_line
            })

    # 🆕 Get all legal moves in UCI
    legal_moves = [move.uci() for move in board.legal_moves]

    return {
        "fen": fen,
        "top_moves": moves,
        "legal_moves": legal_moves
    }
