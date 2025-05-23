# scripts/reset_db.py
import os
import sys

# ensure the project root is on PYTHONPATH
repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, repo_root)

from sqlmodel import SQLModel

import app.models  # now this will import correctly
from app.db import engine

# (re)create all tables
SQLModel.metadata.create_all(engine)
print("✅ DB reset to models")
