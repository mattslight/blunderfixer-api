# === app/models.py ===
from datetime import datetime
from uuid import uuid4

from sqlmodel import JSON, Column, Field, SQLModel


class ArchiveMonth(SQLModel, table=True):
    id: str = Field(default_factory=lambda: str(uuid4()), primary_key=True)
    username: str = Field(index=True)
    month: str  # e.g. "2025-04"
    raw_json: dict = Field(sa_column=Column(JSON, nullable=False))
    fetched_at: datetime = Field(default_factory=datetime.utcnow)
    processed: bool = Field(default=False, index=True)


class Game(SQLModel, table=True):
    id: str = Field(default_factory=lambda: str(uuid4()), primary_key=True)
    username: str = Field(index=True)
    game_uuid: str = Field(index=True)
    url: str
    played_at: datetime
    time_class: str
    time_control: str
    result: str
    eco: str
    pgn: str
    raw: dict = Field(sa_column=Column(JSON, nullable=False))
