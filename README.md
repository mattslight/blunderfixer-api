# blunderfixer-api

This FastAPI service powers the chess training features of **BlunderFixer**. A running instance exposes interactive docs at `/docs` and `/redoc`.

## Endpoints overview

### Health
- `GET /health` – simple status check.
- `GET /` – root heartbeat.

### Analysis
- `POST /analyse-fen` – evaluate a FEN position with Stockfish. Accepts `{ "fen": "...", "top_n": 1 }`.
- `POST /analyse-pgn` – depth‑limited evaluation for each move in a PGN.
- `POST /analyse-pgn-full` – return evaluation plus top engine moves for every ply. Query params: `top_n`, `depth`.
- `POST /extract-features` – extract positional features from a FEN for LLM coaching.
- `POST /phase` – tag each move in a PGN with its game phase.
- `POST /coach` – conversational coach using Stockfish and OpenAI. Requires FEN, legal moves and chat history.
- `GET  /public/players/{username}/recent-games` – fetch and normalise recent games from Chess.com.

### Drill management
- `GET  /drills` – list drill positions. Supports filtering by username, eval swing, phase, opponent and more. `recent_first=true` orders by last played.
- `GET  /drills/recent` – drills you've played recently.
- `GET  /drills/mastered` – drills where your last five attempts were passes.
- `GET  /drills/{id}` – retrieve a drill with game info, history, PGN and engine winning lines.
- `PATCH /drills/{id}` – update a drill (e.g. `{ "archived": true }` or mark as played).
- `GET  /drills/{id}/history` – list history entries for a drill.
- `POST /drills/{id}/history` – record a pass/fail result (any losing moves and final eval) for a drill.
- Drill responses now include a `time_used` field with seconds spent on the losing move.

### Sync jobs
- `POST /sync` – create a job to sync a single user's games.
- `GET  /sync/{job_id}` – check job status and progress counters.
- `POST /sync_all` – enqueue sync jobs for all active users.

### Player statistics
- `GET /player_stats/{username}` – aggregated stats including win rates, openings and rating progression.
- `GET /player_stats/{username}/blunders_fixed` – total passes recorded for that user's drills.

## Contributing

Run the API locally with:

```bash
make dev
```

No automated tests are included yet, so verify changes manually and keep this README current.
Run `python scripts/backfill_time_used.py` if your database predates the `time_used` column.
