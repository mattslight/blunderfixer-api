# Drills Service Refactor

This repository previously exposed all `/drills` endpoints from a single
`app/routes/drills.py` module.  As functionality grew the file became harder to
maintain.  The routing, query logic and domain rules were intermixed which made
onboarding and testing difficult.

The API has been refactored into a small service layer which isolates business
logic from FastAPI specific code.

```
app/
  routes/
    drills/
      __init__.py      # exports `router`
      handlers.py      # FastAPI handlers calling the service
  services/
    drills_service.py  # `DrillService` with all drill operations
```

The new `DrillService` class encapsulates all database access and domain rules.
Handlers extract HTTP parameters and delegate to this service.  Existing
endpoints are preserved:

- `GET  /drills`
- `GET  /drills/recent`
- `GET  /drills/{id}`
- `GET  /drills/{id}/history`
- `POST /drills/{id}/history`
- `PATCH /drills/{id}`

`app/main.py` now imports `router` from `app.routes.drills` (the new package) so
clients continue to use the same URLs.
