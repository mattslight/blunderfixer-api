import chess
import chess.engine
from typing import List

STOCKFISH_PATH = "/opt/homebrew/bin/stockfish"  # Adjust as needed

def analyze_fen(fen: str, depth: int = 15, top_n: int = 1) -> dict:
    board = chess.Board(fen)
    moves = []

    with chess.engine.SimpleEngine.popen_uci(STOCKFISH_PATH) as engine:
        try:
            result = engine.analyse(board, chess.engine.Limit(depth=depth), multipv=top_n)
        except Exception as e:
            return {"error": f"Stockfish failed: {str(e)}"}

        if not isinstance(result, list):
            result = [result]

        for entry in result:
            if "pv" not in entry or not entry["pv"]:
                continue  # skip incomplete lines

            move = entry["pv"][0].uci()
            score_obj = entry["score"].white()

            if score_obj.is_mate():
                evaluation = f"# {score_obj.mate()}"
            else:
                evaluation = round(score_obj.score() / 100, 2)

            moves.append({
                "move": move,
                "evaluation": evaluation
            })

    return {
        "fen": fen,
        "top_moves": moves
    }
