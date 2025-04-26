from fastapi import FastAPI
from app.routes import games, profile, analyse_fen, analyse_pgn, openings, phase, explain_lines, coach_chat 
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(analyse_fen.router)
app.include_router(analyse_pgn.router)
app.include_router(coach_chat.router)
app.include_router(explain_lines.router)
app.include_router(games.router)
app.include_router(openings.router)
app.include_router(phase.router)
app.include_router(profile.router)


@app.get("/health")
def health_check():
    return {"status": "ok"}




