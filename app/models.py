from datetime import datetime, timezone
from typing import List, Optional
from uuid import uuid4

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
)
from sqlmodel import JSON, Field, Relationship, SQLModel


class ArchiveMonth(SQLModel, table=True):
    __table_args__ = ({"comment": "Raw monthly JSON dumps from Chess.com"},)

    id: str = Field(default_factory=lambda: str(uuid4()), primary_key=True)
    username: str = Field(sa_column=Column(String, index=True))
    month: str = Field(sa_column=Column(String))
    raw_json: dict = Field(sa_column=Column(JSON, nullable=False))
    fetched_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_column=Column(DateTime(timezone=True)),
    )
    processed: bool = Field(
        default=False,
        sa_column=Column(Boolean, nullable=False, index=True),
    )


class Game(SQLModel, table=True):
    __table_args__ = (
        UniqueConstraint("game_uuid", name="uq_game_uuid"),
        {"comment": "One row per imported Chess.com game"},
    )

    id: str = Field(default_factory=lambda: str(uuid4()), primary_key=True)
    game_uuid: str = Field(sa_column=Column(String, unique=True, index=True))
    url: str = Field(sa_column=Column(String))
    played_at: datetime = Field(sa_column=Column(DateTime(timezone=True)))
    end_time: datetime = Field(sa_column=Column(DateTime(timezone=True)))
    time_class: str = Field(sa_column=Column(String))
    time_control: str = Field(sa_column=Column(String))
    white_username: str = Field(sa_column=Column(String, index=True))
    white_rating: int = Field(sa_column=Column(Integer))
    white_result: str = Field(sa_column=Column(String))
    black_username: str = Field(sa_column=Column(String, index=True))
    black_rating: int = Field(sa_column=Column(Integer))
    black_result: str = Field(sa_column=Column(String))
    eco: str = Field(sa_column=Column(String))
    eco_url: Optional[str] = Field(
        default=None,
        sa_column=Column(String),
    )
    pgn: str = Field(sa_column=Column(String))
    raw: dict = Field(sa_column=Column(JSON, nullable=False))
    drill_queue: List["DrillQueue"] = Relationship(back_populates="game")
    drill_positions: List["DrillPosition"] = Relationship(back_populates="game")


class DrillQueue(SQLModel, table=True):
    __table_args__ = (
        UniqueConstraint("game_id", "hero_username", name="uq_drillqueue_game_hero"),
        {"comment": "Queue of games to drill per user (hero)"},
    )

    id: str = Field(default_factory=lambda: str(uuid4()), primary_key=True)
    game_id: str = Field(
        sa_column=Column(
            String,
            ForeignKey("game.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
    )
    hero_username: str = Field(
        sa_column=Column(
            String,
            nullable=False,
            index=True,
        ),
    )
    drills_processed: bool = Field(
        default=False,
        sa_column=Column(Boolean, nullable=False),
    )
    drilled_at: Optional[datetime] = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True)),
    )
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )
    game: Optional[Game] = Relationship(back_populates="drill_queue")


class DrillPosition(SQLModel, table=True):
    __table_args__ = (
        UniqueConstraint(
            "game_id", "username", "ply", name="uq_drillposition_game_user_ply"
        ),
        {"comment": "Single Practice Position extracted from games in DrillQueue"},
    )

    id: Optional[int] = Field(default=None, primary_key=True)
    game_id: str = Field(
        sa_column=Column(String, ForeignKey("game.id"), nullable=False)
    )
    game: "Game" = Relationship(back_populates="drill_positions")

    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )

    username: str = Field(sa_column=Column(String, nullable=False))
    fen: str = Field(sa_column=Column(String, nullable=False))
    ply: int = Field(sa_column=Column(Integer, nullable=False))
    eval_swing: float = Field(sa_column=Column(Float, nullable=False))
    initial_eval: float = Field(sa_column=Column(Float, nullable=False))

    white_minor_count: int = Field(default=0, sa_column=Column(Integer))
    black_minor_count: int = Field(default=0, sa_column=Column(Integer))
    white_rook_count: int = Field(default=0, sa_column=Column(Integer))
    black_rook_count: int = Field(default=0, sa_column=Column(Integer))
    white_queen: bool = Field(default=False, sa_column=Column(Boolean))
    black_queen: bool = Field(default=False, sa_column=Column(Boolean))

    archived: bool = Field(
        default=False, sa_column=Column(Boolean, nullable=False, server_default="false")
    )

    has_one_winning_move: bool = Field(
        default=False,
        sa_column=Column(Boolean, nullable=False, server_default="false"),
    )

    winning_moves: Optional[list[str]] = Field(
        default=None, sa_column=Column(JSON, nullable=True)
    )

    losing_move: Optional[str] = Field(
        default=None, sa_column=Column(String, nullable=True)
    )

    history: List["DrillHistory"] = Relationship(back_populates="drill_position")

    last_drilled_at: Optional[datetime] = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), nullable=True),
    )


class DrillHistory(SQLModel, table=True):
    __tablename__ = "drillhistory"

    id: Optional[int] = Field(default=None, primary_key=True)
    drill_position_id: int = Field(foreign_key="drillposition.id", nullable=False)
    result: str = Field(sa_column=Column(String, nullable=False))  # 'pass' | 'fail'
    reason: str = Field(sa_column=Column(String, nullable=True))
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )

    drill_position: "DrillPosition" = Relationship(back_populates="history")


class Job(SQLModel, table=True):
    __table_args__ = ({"comment": "Background sync job records"},)

    id: str = Field(default_factory=lambda: str(uuid4()), primary_key=True)
    username: str = Field(sa_column=Column(String, index=True))
    action: str = Field(sa_column=Column(String))
    status: str = Field(sa_column=Column(String))
    total: int = Field(default=0, sa_column=Column(Integer))
    processed: int = Field(default=0, sa_column=Column(Integer))
    error: Optional[str] = Field(
        default=None,
        sa_column=Column(String),
    )
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_column=Column(DateTime(timezone=True)),
    )
    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_column=Column(DateTime(timezone=True)),
    )


class ActiveUser(SQLModel, table=True):
    __tablename__ = "active_users"
    __table_args__ = ({"comment": "Active users, cron will sync these"},)

    id: Optional[int] = Field(default=None, primary_key=True)
    username: str = Field(
        sa_column=Column(String, nullable=False, unique=True, index=True)
    )
    last_synced: Optional[datetime] = Field(
        default=None, sa_column=Column(DateTime(timezone=True))
    )
