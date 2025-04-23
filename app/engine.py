import chess
import chess.engine

STOCKFISH_PATH = "/opt/homebrew/bin/stockfish"  # Replace with your actual path

def analyze_fen(fen: str, depth: int = 15):
    board = chess.Board(fen)
    with chess.engine.SimpleEngine.popen_uci(STOCKFISH_PATH) as engine:
        result = engine.analyse(board, chess.engine.Limit(depth=depth))
        score = result["score"].white().score(mate_score=10000)  # mate=10000 as convention
        best_move = result["pv"][0].uci()
        return {
            "best_move": best_move,
            "evaluation": score
        }

