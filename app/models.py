from datetime import datetime
from typing import Optional
from uuid import uuid4

from sqlalchemy import Boolean, Column, DateTime, Integer, String, UniqueConstraint
from sqlmodel import JSON, Field, SQLModel


class ArchiveMonth(SQLModel, table=True):
    __table_args__ = ({"comment": "Raw monthly JSON dumps from Chess.com"},)

    id: str = Field(default_factory=lambda: str(uuid4()), primary_key=True)
    username: str = Field(
        sa_column=Column(
            String, index=True, comment="Chess.com username for this archive"
        )
    )
    month: str = Field(
        sa_column=Column(String, comment="Archive month in YYYY-MM format")
    )
    raw_json: dict = Field(
        sa_column=Column(
            JSON, nullable=False, comment="Full JSON payload for the month"
        )
    )
    fetched_at: datetime = Field(
        default_factory=datetime.utcnow,
        sa_column=Column(
            DateTime(timezone=True), comment="When this archive was fetched"
        ),
    )
    processed: bool = Field(
        default=False,
        sa_column=Column(
            Boolean,
            nullable=False,
            index=True,
            comment="True once unpacked into Game rows",
        ),
    )


class Game(SQLModel, table=True):
    __table_args__ = (
        UniqueConstraint("game_uuid", name="uq_game_uuid"),
        {"comment": "One row per imported Chess.com game"},
    )

    id: str = Field(default_factory=lambda: str(uuid4()), primary_key=True)
    game_uuid: str = Field(
        sa_column=Column(String, unique=True, index=True, comment="Chess.com game UUID")
    )
    url: str = Field(sa_column=Column(String, comment="Link to the game on Chess.com"))
    played_at: datetime = Field(
        sa_column=Column(
            DateTime(timezone=True), comment="UTC timestamp when the game was played"
        )
    )
    end_time: datetime = Field(
        sa_column=Column(
            DateTime(timezone=True), comment="UTC timestamp when the game ended"
        )
    )
    time_class: str = Field(
        sa_column=Column(String, comment="Time class: bullet, blitz, rapid, etc.")
    )
    time_control: str = Field(
        sa_column=Column(String, comment="Time control string, e.g. '180+2'")
    )
    white_username: str = Field(
        sa_column=Column(String, index=True, comment="White player's username")
    )
    white_rating: int = Field(
        sa_column=Column(Integer, comment="White player's rating at game time")
    )
    white_result: str = Field(
        sa_column=Column(String, comment="Raw result from white's perspective")
    )
    black_username: str = Field(
        sa_column=Column(String, index=True, comment="Black player's username")
    )
    black_rating: int = Field(
        sa_column=Column(Integer, comment="Black player's rating at game time")
    )
    black_result: str = Field(
        sa_column=Column(String, comment="Raw result from black's perspective")
    )
    eco: str = Field(sa_column=Column(String, comment="ECO code, e.g. 'B12'"))
    eco_url: Optional[str] = Field(
        default=None,
        sa_column=Column(String, comment="Link to the opening on Chess.com"),
    )
    pgn: str = Field(sa_column=Column(String, comment="Full PGN text of the game"))
    raw: dict = Field(
        sa_column=Column(JSON, nullable=False, comment="Raw JSON object from Chess.com")
    )


class Job(SQLModel, table=True):
    __table_args__ = ({"comment": "Background sync job records"},)

    id: str = Field(default_factory=lambda: str(uuid4()), primary_key=True)
    username: str = Field(
        sa_column=Column(String, index=True, comment="Username for whom we’re syncing")
    )
    action: str = Field(
        sa_column=Column(String, comment="Action type, e.g. 'sync_archives'")
    )
    status: str = Field(
        sa_column=Column(String, comment="queued/running/complete/failed")
    )
    total: int = Field(
        default=0, sa_column=Column(Integer, comment="Number of months to process")
    )
    processed: int = Field(
        default=0, sa_column=Column(Integer, comment="How many months have been done")
    )
    error: Optional[str] = Field(
        default=None,
        sa_column=Column(String, comment="Error message if the job failed"),
    )
    created_at: datetime = Field(
        default_factory=datetime.utcnow,
        sa_column=Column(DateTime(timezone=True), comment="When the job was created"),
    )
    updated_at: datetime = Field(
        default_factory=datetime.utcnow,
        sa_column=Column(DateTime(timezone=True), comment="Last update timestamp"),
    )
