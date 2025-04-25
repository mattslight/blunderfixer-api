from fastapi import FastAPI
from app.routes import games, profile, analyze_fen, openings, phase

app = FastAPI()

app.include_router(games.router)
app.include_router(profile.router)
app.include_router(analyze_fen.router)
app.include_router(openings.router)
app.include_router(phase.router)

@app.get("/health")
def health_check():
    return {"status": "ok"}