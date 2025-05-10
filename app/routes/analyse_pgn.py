import io
import traceback

import chess.engine
import chess.pgn
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

router = APIRouter()

STOCKFISH_PATH = "/opt/homebrew/bin/stockfish"  # or wherever you deploy

# ─── Request & Response models ──────────────────────────────────────────


class AnalyseShallowRequest(BaseModel):
    pgn: str
    depth: int = Query(8, ge=1, le=40, description="Stockfish search depth")


class ShallowNode(BaseModel):
    half_move_index: int  # 0 = before White’s 1st move, 1 = before Black’s 1st…
    fen: str  # position FEN
    eval_cp: float  # centipawn score (positive = White better)
    delta_cp: float  # this.eval_cp – previous.eval_cp


# ─── Endpoint ────────────────────────────────────────────────────────────


@router.post(
    "/analyse-pgn",
    response_model=list[ShallowNode],
    summary="Quick, depth-N evaluation of every ply in a PGN",
)
def analyse_shallow(req: AnalyseShallowRequest):
    try:
        # parse PGN
        pgn_io = io.StringIO(req.pgn)
        game = chess.pgn.read_game(pgn_io)
        if game is None:
            raise HTTPException(400, "Invalid PGN")

        board = game.board()
        nodes: list[ShallowNode] = []
        prev_eval = 0.0

        # spawn Stockfish once for the whole scan
        with chess.engine.SimpleEngine.popen_uci(STOCKFISH_PATH) as engine:
            half_idx = 0
            for move in game.mainline_moves():
                # evaluate *before* the move
                info = engine.analyse(board, chess.engine.Limit(depth=req.depth))
                score = info["score"].white()
                eval_cp = (
                    float(score.score() / 1.0)
                    if not score.is_mate()
                    else (1e4 if score.mate() > 0 else -1e4)
                )

                nodes.append(
                    ShallowNode(
                        half_move_index=half_idx,
                        fen=board.fen(),
                        eval_cp=eval_cp,
                        delta_cp=half_idx == 0 and 0.0 or eval_cp - prev_eval,
                    )
                )

                prev_eval = eval_cp
                board.push(move)
                half_idx += 1

        return nodes

    except Exception as e:
        print("🔥 Error in /analyse-pgn")
        print(traceback.format_exc())  # full traceback in Render logs
        raise HTTPException(500, detail="Internal error, see server logs")
