# === app/db.py ===

import logging
from os import getenv

from sqlmodel import Session, SQLModel, create_engine

import app.models  # registers your models with SQLModel.metadata

# ─── Configure logging ──────────────────────────────────────────────────────
# (you can also put this in main.py if you prefer one central place)
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("app.db")

# ─── Read the URL ────────────────────────────────────────────────────
DATABASE_URL = getenv("DATABASE_URL", "sqlite:///./blunderfixer.db")

# ─── Create engine ─────────────────────────────────────────────────────────
engine = create_engine(
    DATABASE_URL, echo=True, connect_args={"options": "-csearch_path=public"}
)

# Ensure all tables exist (idempotent)
SQLModel.metadata.create_all(engine)

# Immediately after creating the engine, log what SQLAlchemy thinks the URL is:
# this will expand sqlite file paths or canonicalize postgres URLs
logger.info(f"🚒 Engine connected to: {engine.url!s}")


# ─── Session factory ───────────────────────────────────────────────────────
def get_session():
    with Session(engine) as session:
        yield session
