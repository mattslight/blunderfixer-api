# === app/db.py ===

import logging
from os import getenv

from sqlmodel import Session, create_engine

# ─── Configure logging ──────────────────────────────────────────────────────
# (you can also put this in main.py if you prefer one central place)
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("app.db")

# ─── Read the URL ────────────────────────────────────────────────────
DATABASE_URL = getenv("DATABASE_URL", "sqlite:///./blunderfixer.db")

# ─── Create engine ─────────────────────────────────────────────────────────
engine = create_engine(DATABASE_URL, echo=True)

# Immediately after creating the engine, log what SQLAlchemy thinks the URL is:
# this will expand sqlite file paths or canonicalize postgres URLs
logger.info(f"🚒 Engine connected to: {engine.url!s}")


# ─── Session factory ───────────────────────────────────────────────────────
def get_session():
    with Session(engine) as session:
        yield session
