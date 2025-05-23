# scripts/reset_db.py
from sqlmodel import SQLModel

import app.models  # so your models get registered
from app.db import engine

# (re)create all tables
SQLModel.metadata.create_all(engine)
print("✅ DB reset to models")
