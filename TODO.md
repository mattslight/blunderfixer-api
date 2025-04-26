# BlunderFixer ‼️ — TODO

## Backend

- [ ] Wire up `python-chess-annotator` to `blunderfixer-api`
- [ ] Create `/annotate` API endpoint that runs PGN through `python-chess-annotator`
- [ ] Create API endpoint to pass annotated PGN to LLM
- [ ] Create LLM workflow:
  - Input: annotated PGN + move number
  - Output: `coach_move_insight_json`
- [ ] For each game, generate a `coach_game_summary_json`

## Frontend

- [ ] Decide on frontend stack:
  - Options: `Next.js`, `React Native`, etc.
  - Must support fast porting to mobile
- [ ] Wire up Chessboard JS/JSX to render game PGNs
- [ ] Build `/profile/{username}` screen
  - [ ] Fetch and display user summary via `/api/route/profile`
  - [ ] (1) Show profile summary
  - [ ] (2) Browse Chess.com game history
  - [ ] (3) Click game to:
    - Run analysis pipeline
    - Display board with key moments
    - Show overall game summary
    - Walk through move-by-move `coach_move_insight_json`

---

### `coach_move_insight_json` Example

```javascript
{
  move: "15. Rfd1",
  mistake_type: "Positional",
  phase: "Middlegame",
  summary: "Ignored kingside danger, reinforced wrong plan.",
  better_move: "15. h3",
  why_better: [
    "Stops Black's h-pawn from advancing to h3 itself.",
    "Secures g4-square and delays kingside collapse.",
    "Buys time for regrouping (e.g. Rad1 later)."
  ],
  strategic_errors: [
    {
      label: "Wrong Prioritization",
      explanation: "Still fails to address the kingside threats (hxg3, g4 pressure)."
    },
    {
      label: "Irrelevant Play",
      explanation: "Rfd1 is aimed at the d-file; battle is on the kingside."
    },
    {
      label: "Time Loss",
      explanation: "Wastes a tempo; Black's attack becomes unstoppable."
    }
  ],
  recovery_line: {
    pgn: "15. h3 d5 16. cxd5 cxd4 17. exd4 Ne7 18. Ne3",
    steps: [
      ["15. h3", "Prevents ...h3 from Black"],
      ["16. cxd5 / 17. exd4", "Challenges center, doesn't give Black full control"],
      ["18. Ne3", "Brings defender to g4/f5"]
    ]
  }
}
```

### `coach_game_summary_json` Example

```javascript
{
  event: "Ultimate Blitz Challenge",
  white: "Fabiano Caruana",
  black: "Garry Kasparov",
  result: "0-1",
  eco: "A05",
  opening: "King's Indian Attack: Symmetrical Defense",

  white_acpl: 59,
  black_acpl: 16,
  key_moment: {
    move_number: 14,
    played: "Ba3",
    better_move: "h3",
    description: "White played Ba3, continuing a queenside plan while Black was preparing a kingside pawn storm. This failed to address the main threat in the position."
  },
  mistake_summary: [
    {
      mistake: "Ignored Kingside Tension",
      why_it_mattered: "Black was preparing a pawn storm; White needed to defend, not counterattack elsewhere."
    },
    {
      mistake: "Misjudged Priorities",
      why_it_mattered: "Queenside activity was secondary; securing the king was urgent."
    },
    {
      mistake: "Lost a Critical Tempo",
      why_it_mattered: "After Ba3, White could no longer easily stop Black’s advancing pawns."
    }
  ],
  coach_summary: "This was a balanced game until move 14. White’s move Ba3 misjudged the position, focusing on the queenside while the kingside required immediate defensive attention. Black steadily increased pressure and converted the advantage with strong attacking play.",
  lesson: "When your opponent starts a pawn storm, respond immediately. Ignoring it can lead to irreversible weaknesses."
}
```
