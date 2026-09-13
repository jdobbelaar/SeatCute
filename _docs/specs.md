# SeatCute — Product Specification (Frontend, Mocked Backend)

## 1. Overview

SeatCute is a waitlist/seating manager for small restaurants with four fixed
table sizes: **1, 2, 4, and 6 seats**. It has three interaction surfaces:

- **Kiosk** (customer-facing, standalone page) — greets arriving parties,
  offers immediate seating or queues them with a projected wait, and lets
  them check/cancel their reservation by phone number.
- **Host** (staff-facing) — manages table occupancy and seats parties from
  the queue.
- **Admin** (staff-facing) — configures table counts and turnover times per
  size.

This phase builds a **real, working frontend** with **all backend/business
logic mocked in the browser** (no server). A future phase will replace the
mock layer with a FastAPI backend persisting to SQLite, without changing the
frontend's UI or call signatures (see §8).

## 2. Decisions & Assumptions Made During Scoping

These were resolved during spec development — flag any that don't match
your intent before handing this off:

1. Tech stack: **plain HTML/CSS/JS**, no framework, no build step.
2. Kiosk is a **separate HTML page** from Admin/Host. Admin and Host share
   one page with a visible toggle between them.
3. Tables are **auto-numbered per size** (e.g. "2-Seat #1", "2-Seat #3") —
   no custom admin labeling.
4. Wait-time projections **account for queue depth** (the Nth person in a
   size's queue is projected onto the Nth-soonest-freeing table of that
   size), not just "soonest table of this size."
5. **No soft-occupy state.** A table is either `available` or `occupied`;
   occupancy (and its turnover timer) starts only when the Host explicitly
   marks a table occupied.
6. Queue entries leave the queue only via: **Cancel** (customer, at kiosk),
   **Seated** (Host), or **Dismissed** (Host, e.g. no-show).
7. If a table of sufficient size is free **and that size's queue is empty**,
   the kiosk sends the party straight to the Host with **no queue record**
   created. If the queue is non-empty, new arrivals always queue (no
   line-skipping even if a table happens to be free).
8. Marking a table occupied is a deliberate **two-click Host transaction**:
   (1) select an available table, then (2) select either a queue entry
   (from *any* size's queue — a small party can be seated at a larger
   table) or a **"Bypass Queue"** action for walk-ins not in the queue.
9. Releasing a table is independent of seating the next party — the Host
   must separately run the seating transaction for whoever's next.
10. Duplicate-phone-number check for joining the queue is **global** (one
    active reservation per phone number across all sizes, not per size).
11. Admin config (table counts, turnover times) is **editable at any time**,
    not a locked one-time setup.
12. State (config, tables, queue) **persists in `localStorage`** so it
    survives page reloads. Kiosk and Admin/Host pages share state via the
    same origin's localStorage.
13. The kiosk asks for the customer's **exact party size** (a number), and
    the app maps it to the smallest sufficient table size. A party larger
    than 6 gets a simple "please speak with our host" message — no queueing
    (documented non-goal, see §7).
14. Times shown to users are **computed at render/interaction time**, not
    live-ticking every second. Screens that stay open with a countdown
    (e.g. Reservation Status) may re-render periodically (e.g. every 15–30s)
    but a smooth per-second clock is out of scope.
15. Reducing a size's table count is **not** blocked by current occupancy.
    Available tables are removed immediately; if that's not enough,
    currently-occupied tables are flagged **pending removal** (highest-
    numbered first) — they keep operating normally, but are deleted
    (instead of returning to available) the next time the Host releases
    them.

Some UI timing constants weren't fully specified in the original brief;
defaults are noted inline below (all should be easy constants to tweak).

## 3. Data Model (mocked via localStorage today; SQLite later)

```
AdminConfig
  sizes: [1, 2, 4, 6]                 // fixed, not configurable
  counts:    { 1: n, 2: n, 4: n, 6: n }   // number of tables per size
  turnover:  { 1: m, 2: m, 4: m, 6: m }   // expected turnover, in minutes

Table
  id: string
  size: 1 | 2 | 4 | 6
  label: string          // e.g. "2-Seat #3", derived from size + index
  status: "available" | "occupied"
  occupiedAt: timestamp | null
  party: { name, phone } | null   // null for Bypass Queue occupancies
  pendingRemoval: boolean   // true = delete (not free) on next release

QueueEntry
  id: string
  name: string
  phone: string
  partySize: number      // exact number the customer entered
  queueSize: 1 | 2 | 4 | 6   // smallest size that fits partySize
  joinedAt: timestamp
```

## 4. Core Business Logic (implemented in mock layer)

**Map party size → queue size**
Smallest value in `[1, 2, 4, 6]` that is `>= partySize`. If `partySize > 6`,
no valid mapping — show the "see the host" message, no queue entry.

**Immediate-seat check** (`queueSize`)
True if: at least one table of `queueSize` is `available`, **and** the
queue for `queueSize` is currently empty.

**Free-time of a table**
- `available` table → free now.
- `occupied` table → `occupiedAt + turnover[size]`.
- Tables flagged `pendingRemoval` are **excluded** from this list entirely
  — they will never become seatable again, so they shouldn't count toward
  anyone's projected wait.

**Projected wait for queue position k (1-indexed) at a given size**
1. Collect free-times for all tables of that size.
2. Sort ascending.
3. Projected time = the k-th value in that sorted list (accounts for
   everyone ahead of them also taking a table).
4. Wait interval = `max(0, projected time - now)`; displayed time-of-day is
   `max(now, projected time)`.

**Seating transaction (Host, two clicks)**
1. Host selects an `available` table (click again to deselect / click a
   different available table to change selection).
2. With a table selected, Host either:
   - clicks **Seat** on a queue entry (any size's queue) → that entry is
     removed from its queue and its `{name, phone}` attached to the table, or
   - clicks **Bypass Queue** → table gets no attached party.
3. Selected table becomes `occupied`, `occupiedAt = now`.

**Release transaction (Host, one click)**
- If `pendingRemoval` is false: occupied table → `available`,
  `occupiedAt = null`, `party = null`.
- If `pendingRemoval` is true: the table is **deleted** from the table
  list entirely, instead of becoming available.
- Either way, does **not** auto-assign the next queue entry — that's a
  separate seating transaction.

**Applying an admin table-count change (size `s`, new target count `T`)**
Let `current` = all not-yet-deleted tables of size `s` (available +
occupied, including any already `pendingRemoval`).
- If `T > current.length`: first clear `pendingRemoval` on existing
  pending tables (lowest-numbered first) until the gap is closed or none
  remain; append new `available` tables (next sequential labels) for any
  remaining increase.
- If `T < current.length`: let `deficit = current.length - T`.
  1. Remove `available` tables (highest-numbered first), up to `deficit`.
  2. If `deficit` remains, flag that many `occupied`, not-yet-pending
     tables (highest-numbered first) as `pendingRemoval = true`. They
     keep counting toward `current` — and keep operating normally — until
     released (see Release transaction above).
- If `T == current.length`: no table-level change.

**Dismiss (Host, one click)**
Removes a queue entry entirely (no-show). No table interaction.

**Cancel (Customer, at kiosk)**
Removes the caller's queue entry entirely.

## 5. Screens & User Stories

### 5.1 Admin View (part of the Admin/Host page)

**US-A1**: As the Admin, I want to set the number of tables and expected
turnover time for each of the four sizes, so the app can manage seating
and wait times correctly.

Acceptance criteria:
- Given the Admin view, when it loads, then it shows one row per size
  (1, 2, 4, 6) with a table-count field and a turnover-minutes field,
  pre-filled from saved config (defaults if none saved yet).
- When Admin changes a count or turnover value and saves, then the config
  is persisted (localStorage) and takes effect immediately.
- When Admin increases a size's count, then any existing pending-removal
  tables of that size are un-flagged first (lowest-numbered first); any
  remaining increase appends new `available` tables with the next
  sequential labels (per §4's table-count-change rule).
- When Admin decreases a size's count and enough `available` tables exist
  to cover the decrease, then the highest-numbered `available` tables are
  removed immediately — no occupied table is touched.
- When Admin decreases a size's count by more than the number of
  currently `available` tables, then all `available` tables of that size
  are removed and the remaining excess is satisfied by flagging that many
  `occupied` tables (highest-numbered first) as **pending removal** —
  those tables keep running normally but are deleted (not freed) the next
  time the Host releases them. Saving is never blocked by occupancy.

### 5.2 Host View (part of the Admin/Host page)

**US-H1**: As the Host, I want to see all tables grouped by size with
their current status, so I know what's open and what's about to turn over.

Acceptance criteria:
- Each table shows its label, status (Available/Occupied), and — if
  occupied — elapsed occupied time and projected free time
  (`occupiedAt + turnover[size]`).
- A table flagged pending-removal shows a distinct indicator (e.g.
  "Occupied — retiring on release") alongside its normal occupied status.

**US-H2**: As the Host, I want to seat a party (from a queue or a walk-in)
at a specific table, so occupancy and timers are tracked accurately.

Acceptance criteria:
- Given no table is selected, when the Host clicks an `available` table,
  then it becomes the selected table (visually highlighted).
- Given a table is selected, when the Host clicks a different available
  table, then selection moves to the new table.
- Given a table is selected, when the Host clicks a different available
  table, then selection moves to the new table; clicking the already-selected table again deselects it.
- Given a table is selected, when the Host clicks **Seat** on a queue
  entry (from any size's queue list), then that table becomes `occupied`
  with `occupiedAt = now`, the entry is removed from its queue, and the
  party's name/phone are attached to the table.
- Given a table is selected, when the Host clicks **Bypass Queue**, then
  that table becomes `occupied` with `occupiedAt = now` and no attached
  party.
- Given no table is selected, **Seat** and **Bypass Queue** controls are
  disabled.

**US-H3**: As the Host, I want to release a table once its party leaves,
so it becomes available for the next seating (or is retired, if the
Admin has scheduled it for removal).

Acceptance criteria:
- Given an occupied table that is **not** pending removal, when the Host
  clicks **Release**, then it becomes `available` with `occupiedAt` and
  `party` cleared.
- Given an occupied table that **is** pending removal, when the Host
  clicks **Release**, then the table is deleted entirely — it no longer
  appears anywhere, rather than becoming available.
- Releasing a table does **not** automatically seat anyone — the next
  queue entry still requires a seating transaction (US-H2).

**US-H4**: As the Host, I want to see each size's queue with wait
estimates, so I can decide who to seat next.

Acceptance criteria:
- Each size's queue is listed in join order, showing name, phone, and the
  current projected wait (recomputed per §4) for that position.

**US-H5**: As the Host, I want to dismiss a queue entry that never showed
up, so the queue stays accurate.

Acceptance criteria:
- When the Host clicks **Dismiss** on a queue entry, then it's removed
  from the queue with no table interaction.

### 5.3 Kiosk — Welcome Screen

**US-K1**: As an arriving customer, I want to say how many seats my party
needs, so the app can seat me or queue me appropriately.

Acceptance criteria:
- Default/idle screen is Welcome: a party-size prompt and a **Reservation
  Status** button.
- Given a party size ≤ 6, when submitted, then the app maps it to the
  smallest sufficient size and:
  - if that size's table is available **and** its queue is empty →
    "A table is available — please wait for your host." (no queue entry
    created), shown for 5s (default), then Welcome.
  - else → prompts for name and phone number.
- Given a party size > 6, then the app shows "Please speak with our host
  directly for large parties." for 5s (default), then Welcome. No queue
  entry created.

**US-K2**: As a customer who can't be seated immediately, I want to give
my name and phone number to hold my place in line, so I know how long
I'll wait.

Acceptance criteria:
- Given name and phone are submitted, when the phone number already has
  an active queue entry (any size), then the app shows "This phone number
  already has an active reservation." for 5s (default) and returns to
  Welcome without creating a duplicate entry.
- Given the phone number is not already queued, then the app creates a
  queue entry, computes the projected wait (§4), and displays the wait
  interval and time-of-day plus "Return to the kiosk if you'd like to
  cancel" for **10 seconds**, then returns to Welcome.

### 5.4 Kiosk — Reservation Status Screen

**US-K3**: As a waiting customer, I want to check my remaining wait or
cancel, so I can decide whether to keep waiting.

Acceptance criteria:
- Given the customer taps **Reservation Status**, then the app prompts
  for a phone number.
- Given the number matches an active queue entry, then the app shows the
  projected remaining wait interval and time-of-day (floored at
  "0 minutes" / "now" — never negative or in the past), plus **Keep My
  Reservation** and **Cancel** buttons.
  - No button pressed within **15 seconds** → return to Welcome, entry
    unchanged.
  - **Keep My Reservation** tapped → show "Thank You" for **2 seconds**,
    then Welcome; entry unchanged.
  - **Cancel** tapped → remove the queue entry, show "Thank you for
    letting us know. We hope to see you again soon." for 5s (default),
    then Welcome.
- Given the number matches no active entry, then show "No reservation
  found for this number." for **5 seconds**, then Welcome.

## 6. Mock "Backend" Architecture

Implement a single JS module (e.g. `mockApi.js`) exposing async functions
whose **names and signatures mirror the future FastAPI endpoints**, backed
by `localStorage` for now:

```
getConfig()
saveConfig(config)
listTables()
listQueue(size)              // or listQueue() for all sizes
joinQueue({ name, phone, partySize })
findActiveQueueEntryByPhone(phone)
cancelQueueEntry(id)
dismissQueueEntry(id)
seatFromQueue({ tableId, queueEntryId })
seatBypass({ tableId })
releaseTable(tableId)
```

Each mock function is the single place that reads/writes localStorage and
applies the business rules in §4, so swapping in real `fetch()` calls later
only touches this one file. Kiosk and Host/Admin pages both import it and
share state naturally since localStorage is per-origin.

## 7. Non-Goals (this phase)

- No notifications (SMS/push) to customers or Host — matches original
  brief ("does not need notification").
- No authentication/login for Admin or Host.
- No multi-restaurant / multi-location support.
- No support for multiple kiosks or multi-device sync beyond one browser's
  localStorage.
- No handling of party sizes above 6 beyond the simple message in US-K1.
- No live per-second countdown timers — times are computed at
  render/interaction (see Decision #14).
- No editing a queue entry (name/phone/party size) after submission —
  customer must cancel and rejoin.
- No historical reporting, analytics, or audit trail UI.
- No real backend or database yet — see §8.
- No way for the Admin to cancel a pending-removal flag on one specific
  table (only the aggregate count-change logic in US-A1 clears flags,
  by un-flagging the lowest-numbered pending tables first).

## 8. Future Backend Integration (not built now)

A FastAPI backend will later:
- Persist `AdminConfig`, `Table`, and `QueueEntry` to SQLite.
- Expose REST endpoints matching the mock function names in §6.
- Record each mutating action as an event (`config_updated`,
  `table_occupied`, `table_released`, `party_queued`, `party_cancelled`,
  `party_seated`, `party_dismissed`) for future auditing/analytics.

The frontend should have no other changes required beyond pointing
`mockApi.js`'s functions at real HTTP calls.
