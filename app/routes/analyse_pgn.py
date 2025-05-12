import io
import os
import traceback
from typing import List, Optional

import chess.engine
import chess.pgn
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

router = APIRouter()

STOCKFISH_PATH = os.getenv("STOCKFISH_PATH", "/opt/homebrew/bin/stockfish")


class AnalyseShallowRequest(BaseModel):
    pgn: str
    depth: int = Query(12, ge=1, le=40, description="Stockfish search depth")


class AnalysisNodeResponse(BaseModel):
    half_move_index: int  # 1 = after White’s 1st, 2 = after Black’s reply, …
    side: str  # "white" or "black"
    move_number: int  # PGN move number
    san: str  # SAN of the move
    uci: str  # UCI of the move
    fen_before: str  # FEN of the position before the move
    fen_after: str  # FEN after the move
    eval_before: float  # centipawns before
    eval_after: float  # centipawns after
    delta_cp: float  # eval_after − eval_before
    mate_in: Optional[int]  # +N if White mates in N, −N if Black mates in N
    depth: int  # the search depth used


@router.post(
    "/analyse-pgn",
    response_model=List[AnalysisNodeResponse],
    summary="Depth-N evaluation for every ply in a PGN (full data)",
)
def analyse_shallow(req: AnalyseShallowRequest):
    try:
        # ── Parse PGN ────────────────────────────────────────────
        pgn_io = io.StringIO(req.pgn)
        game = chess.pgn.read_game(pgn_io)
        if game is None:
            raise HTTPException(400, "Invalid PGN")

        board = game.board()
        nodes: List[AnalysisNodeResponse] = []

        # ── Spawn Stockfish once ────────────────────────────────
        with chess.engine.SimpleEngine.popen_uci(STOCKFISH_PATH) as engine:
            # 1) get initial eval for “before first move”
            init_info = engine.analyse(board, chess.engine.Limit(depth=req.depth))
            init_score = init_info["score"].white()
            if init_score.is_mate():
                prev_eval = 1e4 if init_score.mate() > 0 else -1e4
            else:
                prev_eval = float(init_score.score())

            half_idx = 1
            for move in game.mainline_moves():
                # capture “before” state
                fen_before = board.fen()
                eval_before = prev_eval
                move_san = board.san(move)
                move_uci = move.uci()
                side = "white" if half_idx % 2 == 1 else "black"
                move_number = (half_idx + 1) // 2

                # apply the move
                board.push(move)

                # 2) evaluate “after” state
                info = engine.analyse(board, chess.engine.Limit(depth=req.depth))
                score = info["score"].white()
                if score.is_mate():
                    mate_in = score.mate()
                    eval_after = 1e4 if mate_in > 0 else -1e4
                else:
                    mate_in = None
                    eval_after = float(score.score())

                # compute delta
                delta_cp = eval_after - eval_before

                # record the full node
                nodes.append(
                    AnalysisNodeResponse(
                        half_move_index=half_idx,
                        side=side,
                        move_number=move_number,
                        san=move_san,
                        uci=move_uci,
                        fen_before=fen_before,
                        fen_after=board.fen(),
                        eval_before=eval_before,
                        eval_after=eval_after,
                        delta_cp=delta_cp,
                        mate_in=mate_in,
                        depth=req.depth,
                    )
                )

                # prepare for next ply
                prev_eval = eval_after
                half_idx += 1

        return nodes

    except HTTPException:
        # propagate 4xx
        raise
    except Exception:
        # log full traceback for 5xx
        print("🔥 Error in /analyse-pgn")
        traceback.print_exc()
        raise HTTPException(500, detail="Internal error, see server logs")
