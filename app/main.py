from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from sqlmodel import SQLModel

from app.db import engine
from app.routes import (
    analyse_fen,
    analyse_pgn,
    analyse_pgn_full,
    coach,
    drills,
    fen_feature_extraction,
    phase,
    player_recent_games,
    sync,
)
from app.routes.player_stats.index import router as player_stats_router

app = FastAPI()


# 🌟 Create all tables on startup
@app.on_event("startup")
def on_startup():
    SQLModel.metadata.create_all(engine)


origins = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",  # Local dev
    "https://blunderfixer.com",  # Production frontend
    "https://www.blunderfixer.com",  # Production alias (just in case)
    "https://blunderfixer.vercel.app",  # Preview (Staging) frontend
]


# 🌟 Middleware to log Origin header for every request
@app.middleware("http")
async def log_origin_header(request: Request, call_next):
    origin = request.headers.get("origin")
    if origin:
        print(f"Incoming request Origin: {origin}")
    else:
        print("Incoming request has NO Origin header")
    response = await call_next(request)
    return response


app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(analyse_pgn.router)
app.include_router(analyse_pgn_full.router)
app.include_router(analyse_fen.router)
app.include_router(coach.router)
app.include_router(fen_feature_extraction.router)
app.include_router(phase.router)
app.include_router(player_recent_games.router)
app.include_router(sync.router)
app.include_router(player_stats_router)
app.include_router(drills.router)


@app.get("/health")
def health_check():
    return {"status": "ok"}


@app.get("/")
def root():
    return {"status": "ok"}
