"""SQLAlchemy-backed store implementing _docs/specs.md §4's business rules.

Same method names/signatures as the in-memory MockStore this replaces, so
routers depend on this only through deps.get_store() and never on the
storage mechanism itself. The algorithms here (wait projection, two-click
seating, pending-removal handling) are a direct port of that mock's logic,
adapted to load/mutate ORM rows through a session instead of Python lists.
"""

from __future__ import annotations

import uuid
from typing import Dict, List, Optional

from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from .constants import (
    DEFAULT_COUNTS,
    DEFAULT_TURNOVER,
    SIZES,
    label_index,
    map_party_size_to_queue_size,
    normalize_phone,
    now_ms,
)
from .db import ConfigRow, CounterRow, QueueEntryRow, TableRow, init_db
from .errors import DuplicatePhoneError, NotFoundError, PartyTooLargeError, TableUnavailableError


def _make_table_row(size: int, index: int) -> TableRow:
    return TableRow(
        id=f"t_{size}_{index}",
        size=size,
        label=f"{size}-Seat #{index}",
        status="available",
        pending_removal=False,
    )


class SqlAlchemyStore:
    def __init__(self, engine: Engine) -> None:
        init_db(engine)
        self._session_factory = sessionmaker(bind=engine, expire_on_commit=False)
        self._ensure_seeded()

    def _ensure_seeded(self) -> None:
        with self._session_factory() as session:
            if session.get(ConfigRow, SIZES[0]) is not None:
                return  # already seeded (e.g. reopening an existing database)

            for size in SIZES:
                session.add(ConfigRow(size=size, count=DEFAULT_COUNTS[size], turnover_minutes=DEFAULT_TURNOVER[size]))
                session.add(CounterRow(size=size, next_index=1))
            session.commit()

            for size in SIZES:
                counter = session.get(CounterRow, size)
                for _ in range(DEFAULT_COUNTS[size]):
                    session.add(_make_table_row(size, counter.next_index))
                    counter.next_index += 1
            session.commit()

    # ---- config ---------------------------------------------------------

    def get_config(self) -> dict:
        with self._session_factory() as session:
            counts = {}
            turnover = {}
            for size in SIZES:
                row = session.get(ConfigRow, size)
                counts[str(size)] = row.count
                turnover[str(size)] = row.turnover_minutes
            return {"sizes": list(SIZES), "counts": counts, "turnover": turnover}

    def save_config(self, counts: Dict[int, int], turnover: Dict[int, int]) -> dict:
        with self._session_factory() as session:
            for size in SIZES:
                self._apply_table_count_change(session, size, counts[size])
                row = session.get(ConfigRow, size)
                row.count = counts[size]
                row.turnover_minutes = turnover[size]
            session.commit()
        return self.get_config()

    def _apply_table_count_change(self, session: Session, size: int, target_count: int) -> None:
        current = session.query(TableRow).filter(TableRow.size == size).all()
        current_count = len(current)

        if target_count > current_count:
            remaining = target_count - current_count
            pending = sorted(
                (t for t in current if t.pending_removal),
                key=lambda t: label_index(t.label),
            )
            for t in pending:
                if remaining <= 0:
                    break
                t.pending_removal = False
                remaining -= 1

            if remaining > 0:
                counter = session.get(CounterRow, size)
                for _ in range(remaining):
                    session.add(_make_table_row(size, counter.next_index))
                    counter.next_index += 1

        elif target_count < current_count:
            deficit = current_count - target_count
            available_sorted = sorted(
                (t for t in current if t.status == "available"),
                key=lambda t: -label_index(t.label),
            )
            for t in available_sorted:
                if deficit <= 0:
                    break
                session.delete(t)
                deficit -= 1

            if deficit > 0:
                occupied_sorted = sorted(
                    (t for t in current if t.status == "occupied" and not t.pending_removal),
                    key=lambda t: -label_index(t.label),
                )
                for t in occupied_sorted:
                    if deficit <= 0:
                        break
                    t.pending_removal = True
                    deficit -= 1

    # ---- §4 core business logic ------------------------------------------

    def _free_times_for_size(self, session: Session, size: int) -> List[int]:
        now = now_ms()
        turnover_ms = session.get(ConfigRow, size).turnover_minutes * 60_000
        rows = (
            session.query(TableRow)
            .filter(TableRow.size == size, TableRow.pending_removal.is_(False))
            .all()
        )
        times = [now if t.status == "available" else t.occupied_at + turnover_ms for t in rows]
        times.sort()
        return times

    def _is_immediate_seat_available(self, session: Session, size: int) -> bool:
        has_available = (
            session.query(TableRow).filter(TableRow.size == size, TableRow.status == "available").first()
            is not None
        )
        queue_empty = session.query(QueueEntryRow).filter(QueueEntryRow.queue_size == size).first() is None
        return has_available and queue_empty

    # ---- tables -----------------------------------------------------------

    def list_tables(self) -> List[dict]:
        now = now_ms()
        with self._session_factory() as session:
            turnover_by_size = {size: session.get(ConfigRow, size).turnover_minutes for size in SIZES}
            rows = session.query(TableRow).all()
            ordered = sorted(rows, key=lambda t: (t.size, label_index(t.label)))

            result = []
            for t in ordered:
                turnover_ms = turnover_by_size[t.size] * 60_000
                free_at = t.occupied_at + turnover_ms if t.status == "occupied" else now
                elapsed = (now - t.occupied_at) // 60_000 if t.status == "occupied" else None
                result.append(self._table_row_to_dict(t) | {"elapsedMinutes": elapsed, "freeAt": free_at})
            return result

    @staticmethod
    def _table_row_to_dict(t: TableRow) -> dict:
        party = {"name": t.party_name, "phone": t.party_phone} if t.party_name is not None else None
        return {
            "id": t.id,
            "size": t.size,
            "label": t.label,
            "status": t.status,
            "occupiedAt": t.occupied_at,
            "party": party,
            "pendingRemoval": t.pending_removal,
        }

    def seat_from_queue(self, table_id: str, queue_entry_id: str) -> dict:
        with self._session_factory() as session:
            table = session.get(TableRow, table_id)
            if table is None:
                raise NotFoundError("Table not found.")
            if table.status != "available":
                raise TableUnavailableError("Table is not available.")

            entry = session.get(QueueEntryRow, queue_entry_id)
            if entry is None:
                raise NotFoundError("Queue entry not found.")

            table.status = "occupied"
            table.occupied_at = now_ms()
            table.party_name = entry.name
            table.party_phone = entry.phone
            session.delete(entry)
            session.commit()
            return self._table_row_to_dict(table)

    def seat_bypass(self, table_id: str) -> dict:
        with self._session_factory() as session:
            table = session.get(TableRow, table_id)
            if table is None:
                raise NotFoundError("Table not found.")
            if table.status != "available":
                raise TableUnavailableError("Table is not available.")

            table.status = "occupied"
            table.occupied_at = now_ms()
            table.party_name = None
            table.party_phone = None
            session.commit()
            return self._table_row_to_dict(table)

    def release_table(self, table_id: str) -> None:
        with self._session_factory() as session:
            table = session.get(TableRow, table_id)
            if table is None:
                raise NotFoundError("Table not found.")

            if table.pending_removal:
                session.delete(table)
            else:
                table.status = "available"
                table.occupied_at = None
                table.party_name = None
                table.party_phone = None
            session.commit()

    # ---- queue --------------------------------------------------------

    def list_queue(self, size: Optional[int] = None) -> List[dict]:
        with self._session_factory() as session:
            sizes = [size] if size is not None else list(SIZES)
            free_times_by_size = {s: self._free_times_for_size(session, s) for s in sizes}

            query = session.query(QueueEntryRow)
            if size is not None:
                query = query.filter(QueueEntryRow.queue_size == size)
            entries = sorted(query.all(), key=lambda q: q.joined_at)

            now = now_ms()
            position_counters: Dict[int, int] = {}
            result = []
            for q in entries:
                position_counters[q.queue_size] = position_counters.get(q.queue_size, 0) + 1
                position = position_counters[q.queue_size]
                free_times = free_times_by_size.get(q.queue_size) or self._free_times_for_size(
                    session, q.queue_size
                )
                projected_at = free_times[position - 1] if len(free_times) >= position else None
                result.append(
                    {
                        "id": q.id,
                        "name": q.name,
                        "phone": q.phone,
                        "partySize": q.party_size,
                        "queueSize": q.queue_size,
                        "joinedAt": q.joined_at,
                        "position": position,
                        "projectedAt": max(now, projected_at) if projected_at is not None else None,
                        "projectedWaitMs": max(0, projected_at - now) if projected_at is not None else None,
                    }
                )
            return result

    def get_wait_estimate(self, party_size: int) -> dict:
        queue_size = map_party_size_to_queue_size(party_size)
        if queue_size is None:
            return {"queueSize": None, "immediate": False, "projectedAt": None, "projectedWaitMs": None}

        with self._session_factory() as session:
            immediate = self._is_immediate_seat_available(session, queue_size)
            position = (
                session.query(QueueEntryRow).filter(QueueEntryRow.queue_size == queue_size).count() + 1
            )
            free_times = self._free_times_for_size(session, queue_size)
            now = now_ms()
            projected_at = free_times[position - 1] if len(free_times) >= position else None

            return {
                "queueSize": queue_size,
                "immediate": immediate,
                "projectedAt": max(now, projected_at) if projected_at is not None else None,
                "projectedWaitMs": max(0, projected_at - now) if projected_at is not None else None,
            }

    def find_active_queue_entry_by_phone(self, phone: str) -> Optional[dict]:
        target = normalize_phone(phone)
        with self._session_factory() as session:
            match = next(
                (q for q in session.query(QueueEntryRow).all() if normalize_phone(q.phone) == target),
                None,
            )
            if match is None:
                return None
            match_id, match_size = match.id, match.queue_size

        views = self.list_queue(size=match_size)
        return next(v for v in views if v["id"] == match_id)

    def join_queue(self, name: str, phone: str, party_size: int) -> dict:
        queue_size = map_party_size_to_queue_size(party_size)
        if queue_size is None:
            raise PartyTooLargeError("Party size exceeds the largest table.")

        target = normalize_phone(phone)
        with self._session_factory() as session:
            if any(normalize_phone(q.phone) == target for q in session.query(QueueEntryRow).all()):
                raise DuplicatePhoneError("This phone number already has an active reservation.")

            entry = QueueEntryRow(
                id=f"q_{uuid.uuid4().hex}",
                name=name.strip(),
                phone=phone.strip(),
                party_size=party_size,
                queue_size=queue_size,
                joined_at=now_ms(),
            )
            session.add(entry)
            session.commit()
            return {
                "id": entry.id,
                "name": entry.name,
                "phone": entry.phone,
                "partySize": entry.party_size,
                "queueSize": entry.queue_size,
                "joinedAt": entry.joined_at,
            }

    def cancel_queue_entry(self, queue_entry_id: str) -> None:
        with self._session_factory() as session:
            entry = session.get(QueueEntryRow, queue_entry_id)
            if entry is None:
                raise NotFoundError("Queue entry not found.")
            session.delete(entry)
            session.commit()

    def dismiss_queue_entry(self, queue_entry_id: str) -> None:
        # Same effect as cancel_queue_entry -- kept as a distinct method since
        # it's a separate Host action (no-show) rather than a customer action.
        self.cancel_queue_entry(queue_entry_id)
