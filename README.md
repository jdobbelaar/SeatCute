# SeatCute

Overview

SeatCute is a waitlist/seating manager for small restaurants with four fixed table sizes: 1, 2, 4, and 6 seats. It has three interaction surfaces:

Kiosk (customer-facing, standalone page) — greets arriving parties, offers immediate seating or queues them with a projected wait, and lets them check/cancel their reservation by phone number.
Host (staff-facing) — manages table occupancy and seats parties from the queue.
Admin (staff-facing) — configures table counts and turnover times per size.

## Frontend

The `frontend/` folder is a plain HTML/CSS/JS implementation (no build step,
no framework) with all backend logic mocked in the browser via
`frontend/js/mockApi.js`, backed by `localStorage`. See `_docs/specs.md` for
the full spec.

- `frontend/index.html` — Host/Admin dashboard (toggle between the two views)
- `frontend/kiosk.html` — customer-facing kiosk

Since it's static files with no build step, serve the `frontend/` folder with
any local static server (opening via `file://` will also mostly work, but a
server avoids browser quirks with `localStorage` isolation), e.g.:

```
uv run python -m http.server 8000 --directory frontend
```

Then open `http://localhost:8000/index.html` (Host/Admin) and
`http://localhost:8000/kiosk.html` (Kiosk) — both read/write the same
`localStorage`, so open them in the same browser to see shared state.