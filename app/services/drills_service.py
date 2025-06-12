from __future__ import annotations

import os
import sys
from datetime import datetime, timezone
from math import ceil
from typing import List, Optional

import chess
import chess.engine
from sqlalchemy import nullsfirst, nullslast, or_
from sqlalchemy.orm import selectinload
from sqlmodel import Session, select

STOCKFISH_PATH = os.getenv("STOCKFISH_PATH", "stockfish")

from app.models import DrillHistory, DrillPosition, Game
from app.routes.fen_feature_extraction import extract_features_from_fen
from app.schemas import (
    DrillHistoryCreate,
    DrillHistoryRead,
    DrillPositionResponse,
    DrillUpdateRequest,
)


class DrillNotFound(Exception):
    """Raised when a drill position cannot be found."""


class InvalidResult(Exception):
    """Raised when a history payload result is invalid."""


def classify_phase(
    ply: int,
    has_white_queen: Optional[bool],
    has_black_queen: Optional[bool],
    white_rook_count: Optional[int],
    black_rook_count: Optional[int],
    white_minor_count: Optional[int],
    black_minor_count: Optional[int],
    opening_move_threshold: int = 10,
) -> str:
    """Return one of opening|middle|late|endgame for a given position."""

    move_no = ceil(ply / 2)

    if None in (
        has_white_queen,
        has_black_queen,
        white_rook_count,
        black_rook_count,
        white_minor_count,
        black_minor_count,
    ):
        return "opening" if move_no < opening_move_threshold else "middle"

    if move_no < opening_move_threshold and (has_white_queen or has_black_queen):
        return "opening"

    white_pts = int(has_white_queen) * 2 + white_rook_count + white_minor_count
    black_pts = int(has_black_queen) * 2 + black_rook_count + black_minor_count
    material = max(white_pts, black_pts)

    if material >= 5:
        return "middle"
    if material >= 3:
        return "late"
    return "endgame"


class DrillService:
    def __init__(self, session: Session) -> None:
        self.session = session

    # ------------------------------------------------------------------
    # Listing drills
    # ------------------------------------------------------------------
    def list_drills(
        self,
        *,
        username: str,
        limit: int = 100,
        opening_threshold: int = 10,
        min_eval_swing: float = 0.0,
        max_eval_swing: float = float("inf"),
        phases: Optional[List[str]] = None,
        hero_results: Optional[List[str]] = None,
        opponent: Optional[str] = None,
        include: Optional[List[str]] = None,
        recent_first: bool = False,
    ) -> List[DrillPositionResponse]:
        min_eval_cp = int(min_eval_swing)
        max_eval_cp = (
            sys.maxsize if max_eval_swing == float("inf") else int(max_eval_swing)
        )

        phase_whitelist = {p.lower() for p in phases or []}
        result_whitelist = {r.lower() for r in hero_results or []}

        include_set = {item.lower() for item in include or []}
        include_archived = "archived" in include_set
        include_mastered = "mastered" in include_set

        batch_size = limit * 4
        offset = 0
        results: List[DrillPositionResponse] = []

        while len(results) < limit:
            filters = [
                DrillPosition.username == username,
                DrillPosition.eval_swing >= min_eval_cp,
                DrillPosition.eval_swing <= max_eval_cp,
            ]
            if not include_archived:
                filters.append(DrillPosition.archived == False)  # noqa: E712

            order_last = (
                nullslast(DrillPosition.last_drilled_at.desc())
                if recent_first
                else nullsfirst(DrillPosition.last_drilled_at.asc())
            )

            query = (
                select(DrillPosition)
                .join(DrillPosition.game)
                .options(
                    selectinload(DrillPosition.game),
                    selectinload(DrillPosition.history),
                )
                .where(*filters)
                .order_by(
                    order_last,
                    Game.played_at.desc(),
                    DrillPosition.created_at.desc(),
                )
                .offset(offset)
                .limit(batch_size)
            )

            if opponent:
                opponent_like = f"%{opponent}%"
                query = query.where(
                    or_(
                        Game.white_username.ilike(opponent_like),
                        Game.black_username.ilike(opponent_like),
                    )
                )

            rows = self.session.exec(query).all()
            if not rows:
                break

            for dp in rows:
                game = dp.game
                hero_is_white = dp.username == game.white_username

                history_sorted = sorted(
                    dp.history, key=lambda h: h.timestamp, reverse=True
                )
                recent = history_sorted[:5]
                mastered = len(recent) == 5 and all(h.result == "pass" for h in recent)

                if not include_mastered and mastered:
                    continue

                hero_raw = game.white_result if hero_is_white else game.black_result
                opp_raw = game.black_result if hero_is_white else game.white_result
                is_draw = game.white_result == game.black_result
                hero_res = "win" if hero_raw == "win" else "draw" if is_draw else "loss"

                if result_whitelist and hero_res not in result_whitelist:
                    continue

                phase = classify_phase(
                    dp.ply,
                    dp.white_queen,
                    dp.black_queen,
                    dp.white_rook_count,
                    dp.black_rook_count,
                    dp.white_minor_count,
                    dp.black_minor_count,
                    opening_threshold,
                )
                if phase_whitelist and phase not in phase_whitelist:
                    continue

                results.append(
                    DrillPositionResponse(
                        id=dp.id,
                        game_id=dp.game_id,
                        username=dp.username,
                        fen=dp.fen,
                        ply=dp.ply,
                        initial_eval=dp.initial_eval,
                        eval_swing=dp.eval_swing,
                        created_at=dp.created_at,
                        hero_result=hero_res,
                        result_reason=opp_raw if hero_res == "win" else hero_raw,
                        time_control=game.time_control,
                        time_class=game.time_class,
                        hero_rating=(
                            game.white_rating if hero_is_white else game.black_rating
                        ),
                        opponent_username=(
                            game.black_username
                            if hero_is_white
                            else game.white_username
                        ),
                        opponent_rating=(
                            game.black_rating if hero_is_white else game.white_rating
                        ),
                        game_played_at=game.played_at,
                        phase=phase,
                        mastered=mastered,
                        archived=dp.archived,
                        has_one_winning_move=dp.has_one_winning_move,
                        winning_moves=dp.winning_moves,
                        winning_lines=dp.winning_lines,
                        losing_move=dp.losing_move,
                        history=[DrillHistoryRead.from_orm(h) for h in dp.history],
                        last_drilled_at=dp.last_drilled_at,
                    )
                )
                if len(results) == limit:
                    break

            offset += batch_size

        return results[:limit]

    # ------------------------------------------------------------------
    # Recent drills
    # ------------------------------------------------------------------
    def recent_drills(
        self,
        *,
        username: str,
        limit: int = 20,
        include_archived: bool = False,
    ) -> List[DrillPositionResponse]:
        stmt = (
            select(DrillPosition)
            .join(DrillPosition.game)
            .options(
                selectinload(DrillPosition.game), selectinload(DrillPosition.history)
            )
            .where(DrillPosition.username == username)
            .where(DrillPosition.last_drilled_at.is_not(None))
            .order_by(DrillPosition.last_drilled_at.desc())
            .limit(limit)
        )
        if not include_archived:
            stmt = stmt.where(DrillPosition.archived == False)  # noqa: E712

        rows = self.session.exec(stmt).all()

        results: List[DrillPositionResponse] = []
        for dp in rows:
            game = dp.game
            hero_is_white = dp.username == game.white_username

            history_sorted = sorted(dp.history, key=lambda h: h.timestamp, reverse=True)
            recent = history_sorted[:5]
            mastered = len(recent) == 5 and all(h.result == "pass" for h in recent)

            hero_raw = game.white_result if hero_is_white else game.black_result
            opp_raw = game.black_result if hero_is_white else game.white_result
            is_draw = game.white_result == game.black_result
            hero_res = "win" if hero_raw == "win" else "draw" if is_draw else "loss"

            results.append(
                DrillPositionResponse(
                    id=dp.id,
                    game_id=dp.game_id,
                    username=dp.username,
                    fen=dp.fen,
                    ply=dp.ply,
                    initial_eval=dp.initial_eval,
                    eval_swing=dp.eval_swing,
                    created_at=dp.created_at,
                    hero_result=hero_res,
                    result_reason=opp_raw if hero_res == "win" else hero_raw,
                    time_control=game.time_control,
                    time_class=game.time_class,
                    hero_rating=(
                        game.white_rating if hero_is_white else game.black_rating
                    ),
                    opponent_username=(
                        game.black_username if hero_is_white else game.white_username
                    ),
                    opponent_rating=(
                        game.black_rating if hero_is_white else game.white_rating
                    ),
                    game_played_at=game.played_at,
                    phase=classify_phase(
                        dp.ply,
                        dp.white_queen,
                        dp.black_queen,
                        dp.white_rook_count,
                        dp.black_rook_count,
                        dp.white_minor_count,
                        dp.black_minor_count,
                    ),
                    mastered=mastered,
                    archived=dp.archived,
                    has_one_winning_move=dp.has_one_winning_move,
                    winning_moves=dp.winning_moves,
                    winning_lines=dp.winning_lines,
                    losing_move=dp.losing_move,
                    history=[DrillHistoryRead.from_orm(h) for h in dp.history],
                    last_drilled_at=dp.last_drilled_at,
                )
            )

        return results

    # ------------------------------------------------------------------
    # Mastered drills
    # ------------------------------------------------------------------
    def mastered_drills(
        self,
        *,
        username: str,
        limit: int = 20,
        include_archived: bool = False,
    ) -> List[DrillPositionResponse]:
        """Return drills that have been mastered (5 recent passes)."""

        stmt = (
            select(DrillPosition)
            .join(DrillPosition.game)
            .options(
                selectinload(DrillPosition.game), selectinload(DrillPosition.history)
            )
            .where(DrillPosition.username == username)
            .where(DrillPosition.last_drilled_at.is_not(None))
            .order_by(DrillPosition.last_drilled_at.desc())
        )
        if not include_archived:
            stmt = stmt.where(DrillPosition.archived == False)  # noqa: E712

        rows = self.session.exec(stmt).all()

        results: List[DrillPositionResponse] = []
        for dp in rows:
            game = dp.game
            hero_is_white = dp.username == game.white_username

            history_sorted = sorted(dp.history, key=lambda h: h.timestamp, reverse=True)
            recent = history_sorted[:5]
            mastered = len(recent) == 5 and all(h.result == "pass" for h in recent)
            if not mastered:
                continue

            hero_raw = game.white_result if hero_is_white else game.black_result
            opp_raw = game.black_result if hero_is_white else game.white_result
            is_draw = game.white_result == game.black_result
            hero_res = "win" if hero_raw == "win" else "draw" if is_draw else "loss"

            results.append(
                DrillPositionResponse(
                    id=dp.id,
                    game_id=dp.game_id,
                    username=dp.username,
                    fen=dp.fen,
                    ply=dp.ply,
                    initial_eval=dp.initial_eval,
                    eval_swing=dp.eval_swing,
                    created_at=dp.created_at,
                    hero_result=hero_res,
                    result_reason=opp_raw if hero_res == "win" else hero_raw,
                    time_control=game.time_control,
                    time_class=game.time_class,
                    hero_rating=(
                        game.white_rating if hero_is_white else game.black_rating
                    ),
                    opponent_username=(
                        game.black_username if hero_is_white else game.white_username
                    ),
                    opponent_rating=(
                        game.black_rating if hero_is_white else game.white_rating
                    ),
                    game_played_at=game.played_at,
                    phase=classify_phase(
                        dp.ply,
                        dp.white_queen,
                        dp.black_queen,
                        dp.white_rook_count,
                        dp.black_rook_count,
                        dp.white_minor_count,
                        dp.black_minor_count,
                    ),
                    mastered=mastered,
                    archived=dp.archived,
                    has_one_winning_move=dp.has_one_winning_move,
                    winning_moves=dp.winning_moves,
                    winning_lines=dp.winning_lines,
                    losing_move=dp.losing_move,
                    history=[DrillHistoryRead.from_orm(h) for h in dp.history],
                    last_drilled_at=dp.last_drilled_at,
                )
            )
            if len(results) == limit:
                break

        return results

    # ------------------------------------------------------------------
    # Single drill retrieval
    # ------------------------------------------------------------------
    def get_drill(self, *, drill_id: int) -> DrillPositionResponse:
        stmt = (
            select(DrillPosition)
            .where(DrillPosition.id == drill_id)
            .options(
                selectinload(DrillPosition.game),
                selectinload(DrillPosition.history),
            )
        )
        drill: DrillPosition | None = self.session.exec(stmt).one_or_none()
        if not drill:
            raise DrillNotFound()

        game = drill.game
        hero_is_white = drill.username == game.white_username

        hero_raw = game.white_result if hero_is_white else game.black_result
        opp_raw = game.black_result if hero_is_white else game.white_result
        is_draw = game.white_result == game.black_result
        hero_res = "win" if hero_raw == "win" else "draw" if is_draw else "loss"

        phase = classify_phase(
            drill.ply,
            drill.white_queen,
            drill.black_queen,
            drill.white_rook_count,
            drill.black_rook_count,
            drill.white_minor_count,
            drill.black_minor_count,
        )

        history_sorted = sorted(drill.history, key=lambda h: h.timestamp, reverse=True)
        recent = history_sorted[:5]
        mastered = len(recent) == 5 and all(h.result == "pass" for h in recent)

        features = extract_features_from_fen(drill.fen)

        return DrillPositionResponse(
            id=drill.id,
            game_id=drill.game_id,
            username=drill.username,
            fen=drill.fen,
            ply=drill.ply,
            initial_eval=drill.initial_eval,
            eval_swing=drill.eval_swing,
            created_at=drill.created_at,
            hero_result=hero_res,
            result_reason=opp_raw if hero_res == "win" else hero_raw,
            time_control=game.time_control,
            time_class=game.time_class,
            hero_rating=game.white_rating if hero_is_white else game.black_rating,
            opponent_username=(
                game.black_username if hero_is_white else game.white_username
            ),
            opponent_rating=game.black_rating if hero_is_white else game.white_rating,
            game_played_at=game.played_at,
            pgn=game.pgn,
            phase=phase,
            mastered=mastered,
            archived=drill.archived,
            has_one_winning_move=drill.has_one_winning_move,
            winning_moves=drill.winning_moves,
            winning_lines=drill.winning_lines,
            losing_move=drill.losing_move,
            features=features,
            history=[DrillHistoryRead.from_orm(h) for h in drill.history],
            last_drilled_at=drill.last_drilled_at,
        )

    # ------------------------------------------------------------------
    # Drill history
    # ------------------------------------------------------------------
    def read_drill_history(self, *, drill_id: int) -> List[DrillHistoryRead]:
        statement = (
            select(DrillHistory)
            .where(DrillHistory.drill_position_id == drill_id)
            .order_by(DrillHistory.timestamp.desc())
        )
        return self.session.exec(statement).all()

    def create_drill_history(
        self,
        *,
        drill_id: int,
        payload: DrillHistoryCreate,
    ) -> DrillHistoryRead:
        result_lower = payload.result.lower()
        if result_lower not in {"pass", "fail"}:
            raise InvalidResult()

        dp = self.session.get(DrillPosition, drill_id)
        if not dp:
            raise DrillNotFound()

        ts = payload.timestamp or datetime.now(timezone.utc)
        final_eval = None
        if payload.moves:
            try:
                board = chess.Board(dp.fen)
                for mv in payload.moves:
                    try:
                        board.push_san(mv)
                    except Exception:
                        board.push(chess.Move.from_uci(mv))
                with chess.engine.SimpleEngine.popen_uci(STOCKFISH_PATH) as eng:
                    info = eng.analyse(board, chess.engine.Limit(depth=20))
                score_obj = info["score"]
                mate_score = score_obj.pov(chess.WHITE).mate()
                cp_score = score_obj.pov(chess.WHITE).score()
                if mate_score is not None:
                    raw = 10000 - abs(mate_score)
                    final_eval = raw if mate_score > 0 else -raw
                elif cp_score is not None:
                    final_eval = float(cp_score)
            except Exception:
                final_eval = None
        new_hist = DrillHistory(
            drill_position_id=drill_id,
            result=result_lower,
            reason=payload.reason,
            moves=payload.moves or [],
            final_eval=final_eval,
            timestamp=ts,
        )

        dp.last_drilled_at = ts
        self.session.add(new_hist)
        self.session.commit()
        self.session.refresh(new_hist)
        return DrillHistoryRead.from_orm(new_hist)

    # ------------------------------------------------------------------
    # Drill update
    # ------------------------------------------------------------------
    def update_drill(
        self, *, drill_id: int, payload: DrillUpdateRequest
    ) -> DrillPositionResponse:
        dp = self.session.get(DrillPosition, drill_id)
        if not dp:
            raise DrillNotFound()

        if payload.archived is not None:
            dp.archived = payload.archived

        if payload.mark_played:
            dp.last_drilled_at = datetime.now(timezone.utc)

        self.session.add(dp)
        self.session.commit()

        return self.get_drill(drill_id=drill_id)
