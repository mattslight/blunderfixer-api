# === app/models.py ===
from datetime import datetime
from typing import Optional
from uuid import uuid4

from sqlalchemy import Column, String, UniqueConstraint
from sqlmodel import JSON, Column, Field, SQLModel


class ArchiveMonth(SQLModel, table=True):
    id: str = Field(default_factory=lambda: str(uuid4()), primary_key=True)
    username: str = Field(index=True)
    month: str  # e.g. "2025-04"
    raw_json: dict = Field(sa_column=Column(JSON, nullable=False))
    fetched_at: datetime = Field(default_factory=datetime.utcnow)
    processed: bool = Field(default=False, index=True)


class Game(SQLModel, table=True):
    __table_args__ = (UniqueConstraint("game_uuid", name="uq_game_uuid"),)

    id: str = Field(default_factory=lambda: str(uuid4()), primary_key=True)
    username: str = Field(index=True)
    game_uuid: str = Field(sa_column=Column(String, unique=True, index=True))

    url: str
    played_at: datetime
    time_class: str
    time_control: str
    result: str
    opponent_result: Optional[str] = Field(default=None)
    eco: str
    eco_url: Optional[str] = Field(default=None, sa_column=Column(String))
    pgn: str
    raw: dict = Field(sa_column=Column(JSON, nullable=False))


class Job(SQLModel, table=True):
    id: str = Field(default_factory=lambda: str(uuid4()), primary_key=True)
    username: str = Field(index=True)
    action: str
    status: str  # e.g. "queued", "running", "complete", "failed"
    total: int = 0
    processed: int = 0
    error: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
