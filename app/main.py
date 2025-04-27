from fastapi import FastAPI, Request
from app.routes import games, profile, analyse_fen, analyse_pgn, openings, phase, explain_lines, coach_chat 
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI()

origins = [
    "http://localhost:5173",           # Local dev
    "https://blunderfixer.com",        # Production frontend
    "https://www.blunderfixer.com",    # Production alias (just in case)
    "https://blunderfixer.vercel.app", # Preview (Staging) frontend
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

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
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

@app.get("/")
def root():
    return {"status": "ok"}
