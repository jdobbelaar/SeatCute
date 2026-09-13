# SeatCute

Overview

SeatCute is a waitlist/seating manager for small restaurants with four fixed table sizes: 1, 2, 4, and 6 seats. It has three interaction surfaces:

Kiosk (customer-facing, standalone page) — greets arriving parties, offers immediate seating or queues them with a projected wait, and lets them check/cancel their reservation by phone number.
Host (staff-facing) — manages table occupancy and seats parties from the queue.
Admin (staff-facing) — configures table counts and turnover times per size.

## Frontend

The `frontend/` folder is a plain HTML/CSS/JS implementation (no build step,
no framework). All backend calls are centralized in `frontend/js/api.js`,
which talks to the FastAPI backend (`backend/`, see below) over `fetch()`.
See `_docs/specs.md` for the full spec.

- `frontend/index.html` — Host/Admin dashboard (toggle between the two views)
- `frontend/kiosk.html` — customer-facing kiosk
- `frontend/js/constants.js` — `API_BASE_URL` and UI timing constants

The backend must be running for the frontend to work (see Backend below).
Serve the `frontend/` folder with any local static server on a **different
port than the backend** (opening via `file://` will also mostly work, but a
server avoids browser quirks), e.g.:

```
uv run python -m http.server 8080 --directory frontend
```

Then open `http://localhost:8080/index.html` (Host/Admin) and
`http://localhost:8080/kiosk.html` (Kiosk).

## Backend

`backend/` is a FastAPI implementation of `openapi.yaml`, managed with
[uv](https://docs.astral.sh/uv/). It currently uses an in-memory mock store
(`seatcute_backend/store.py`) instead of a real database — same business
rules that used to live in the frontend's mock layer, just re-implemented in
Python — injected via a FastAPI dependency (`seatcute_backend/deps.py`) so it
can be swapped for a real database later without touching the routers.
State resets whenever the backend process restarts.

```
cd backend
uv sync                 # install dependencies into backend/.venv
uv run pytest           # run the test suite
uv run uvicorn seatcute_backend.main:app --reload --app-dir src
```

This starts the API at `http://localhost:8000` (open
`http://localhost:8000/docs` for interactive API docs) with permissive
dev-only CORS enabled, so `frontend/`'s `fetch()` calls from a different
origin/port are allowed. Change `API_BASE_URL` in
`frontend/js/constants.js` if the backend runs somewhere else.