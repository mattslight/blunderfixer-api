from fastapi import FastAPI
from app.routes import games, profile, analyze

app = FastAPI()

app.include_router(games.router)
app.include_router(profile.router)
app.include_router(analyze.router)

@app.get("/health")
def health_check():
    return {"status": "ok"}