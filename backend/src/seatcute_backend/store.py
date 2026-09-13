"""In-memory mock "database" implementing _docs/specs.md §4's business rules.

This mirrors frontend/js/mockApi.js's logic (localStorage there, a plain
Python object here). It's injected into routes via deps.get_store, so a
later real-database-backed store can be swapped in behind the same method
signatures without touching the routers.
"""

from __future__ import annotations

import re
import time
from dataclasses import dataclass, field
from itertools import count
from typing import Dict, List, Optional

from .errors import DuplicatePhoneError, NotFoundError, PartyTooLargeError, TableUnavailableError

SIZES: tuple[int, ...] = (1, 2, 4, 6)
DEFAULT_COUNTS: Dict[int, int] = {1: 2, 2: 4, 4: 3, 6: 1}
DEFAULT_TURNOVER: Dict[int, int] = {1: 30, 2: 45, 4: 60, 6: 90}

_LABEL_INDEX_RE = re.compile(r"#(\d+)$")
_id_seq = count(1)


def _now_ms() -> int:
    return int(time.time() * 1000)


def _normalize_phone(phone: str) -> str:
    return re.sub(r"\D", "", phone)


def _label_index(label: str) -> int:
    match = _LABEL_INDEX_RE.search(label)
    return int(match.group(1)) if match else 0


def map_party_size_to_queue_size(party_size: int) -> Optional[int]:
    fits = [s for s in SIZES if s >= party_size]
    return min(fits) if fits else None


@dataclass
class TableRecord:
    id: str
    size: int
    label: str
    status: str = "available"
    occupied_at: Optional[int] = None
    party: Optional[dict] = None
    pending_removal: bool = False


@dataclass
class QueueEntryRecord:
    id: str
    name: str
    phone: str
    party_size: int
    queue_size: int
    joined_at: int = field(default_factory=_now_ms)


def _make_table(size: int, index: int) -> TableRecord:
    return TableRecord(id=f"t_{size}_{index}", size=size, label=f"{size}-Seat #{index}")


class MockStore:
    def __init__(self) -> None:
        self.counts: Dict[int, int] = dict(DEFAULT_COUNTS)
        self.turnover: Dict[int, int] = dict(DEFAULT_TURNOVER)
        self.tables: List[TableRecord] = []
        self.queue: List[QueueEntryRecord] = []
        self.counters: Dict[int, int] = {}
        for size in SIZES:
            self.counters[size] = 1
            for _ in range(self.counts[size]):
                self.tables.append(_make_table(size, self.counters[size]))
                self.counters[size] += 1

    # ---- config ---------------------------------------------------------

    def get_config(self) -> dict:
        return {
            "sizes": list(SIZES),
            "counts": {str(s): self.counts[s] for s in SIZES},
            "turnover": {str(s): self.turnover[s] for s in SIZES},
        }

    def save_config(self, counts: Dict[int, int], turnover: Dict[int, int]) -> dict:
        for size in SIZES:
            self._apply_table_count_change(size, counts[size])
            self.counts[size] = counts[size]
            self.turnover[size] = turnover[size]
        return self.get_config()

    def _apply_table_count_change(self, size: int, target_count: int) -> None:
        current = [t for t in self.tables if t.size == size]
        current_count = len(current)

        if target_count > current_count:
            remaining = target_count - current_count
            pending = sorted(
                (t for t in current if t.pending_removal),
                key=lambda t: _label_index(t.label),
            )
            for t in pending:
                if remaining <= 0:
                    break
                t.pending_removal = False
                remaining -= 1
            for _ in range(remaining):
                idx = self.counters[size]
                self.counters[size] += 1
                self.tables.append(_make_table(size, idx))

        elif target_count < current_count:
            deficit = current_count - target_count
            available_sorted = sorted(
                (t for t in self.tables if t.size == size and t.status == "available"),
                key=lambda t: -_label_index(t.label),
            )
            for t in available_sorted:
                if deficit <= 0:
                    break
                self.tables.remove(t)
                deficit -= 1

            if deficit > 0:
                occupied_sorted = sorted(
                    (
                        t
                        for t in self.tables
                        if t.size == size and t.status == "occupied" and not t.pending_removal
                    ),
                    key=lambda t: -_label_index(t.label),
                )
                for t in occupied_sorted:
                    if deficit <= 0:
                        break
                    t.pending_removal = True
                    deficit -= 1

    # ---- §4 core business logic ------------------------------------------

    def _free_times_for_size(self, size: int) -> List[int]:
        now = _now_ms()
        turnover_ms = self.turnover[size] * 60_000
        times = [
            (now if t.status == "available" else t.occupied_at + turnover_ms)
            for t in self.tables
            if t.size == size and not t.pending_removal
        ]
        times.sort()
        return times

    def _is_immediate_seat_available(self, size: int) -> bool:
        has_available = any(t.size == size and t.status == "available" for t in self.tables)
        queue_empty = not any(q.queue_size == size for q in self.queue)
        return has_available and queue_empty

    # ---- tables -----------------------------------------------------------

    def list_tables(self) -> List[dict]:
        now = _now_ms()
        ordered = sorted(self.tables, key=lambda t: (t.size, _label_index(t.label)))
        result = []
        for t in ordered:
            turnover_ms = self.turnover[t.size] * 60_000
            free_at = t.occupied_at + turnover_ms if t.status == "occupied" else now
            elapsed = (now - t.occupied_at) // 60_000 if t.status == "occupied" else None
            result.append(self._table_to_dict(t) | {"elapsedMinutes": elapsed, "freeAt": free_at})
        return result

    def _table_to_dict(self, t: TableRecord) -> dict:
        return {
            "id": t.id,
            "size": t.size,
            "label": t.label,
            "status": t.status,
            "occupiedAt": t.occupied_at,
            "party": t.party,
            "pendingRemoval": t.pending_removal,
        }

    def _find_table(self, table_id: str) -> Optional[TableRecord]:
        return next((t for t in self.tables if t.id == table_id), None)

    def seat_from_queue(self, table_id: str, queue_entry_id: str) -> dict:
        table = self._find_table(table_id)
        if table is None:
            raise NotFoundError("Table not found.")
        if table.status != "available":
            raise TableUnavailableError("Table is not available.")

        idx = next((i for i, q in enumerate(self.queue) if q.id == queue_entry_id), None)
        if idx is None:
            raise NotFoundError("Queue entry not found.")
        entry = self.queue.pop(idx)

        table.status = "occupied"
        table.occupied_at = _now_ms()
        table.party = {"name": entry.name, "phone": entry.phone}
        return self._table_to_dict(table)

    def seat_bypass(self, table_id: str) -> dict:
        table = self._find_table(table_id)
        if table is None:
            raise NotFoundError("Table not found.")
        if table.status != "available":
            raise TableUnavailableError("Table is not available.")

        table.status = "occupied"
        table.occupied_at = _now_ms()
        table.party = None
        return self._table_to_dict(table)

    def release_table(self, table_id: str) -> None:
        table = self._find_table(table_id)
        if table is None:
            raise NotFoundError("Table not found.")

        if table.pending_removal:
            self.tables.remove(table)
        else:
            table.status = "available"
            table.occupied_at = None
            table.party = None

    # ---- queue --------------------------------------------------------

    def list_queue(self, size: Optional[int] = None) -> List[dict]:
        sizes = [size] if size is not None else list(SIZES)
        free_times_by_size = {s: self._free_times_for_size(s) for s in sizes}

        entries = [q for q in self.queue if size is None or q.queue_size == size]
        entries.sort(key=lambda q: q.joined_at)

        now = _now_ms()
        position_counters: Dict[int, int] = {}
        result = []
        for q in entries:
            position_counters[q.queue_size] = position_counters.get(q.queue_size, 0) + 1
            position = position_counters[q.queue_size]
            free_times = free_times_by_size.get(q.queue_size) or self._free_times_for_size(q.queue_size)
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

        immediate = self._is_immediate_seat_available(queue_size)
        position = sum(1 for q in self.queue if q.queue_size == queue_size) + 1
        free_times = self._free_times_for_size(queue_size)
        now = _now_ms()
        projected_at = free_times[position - 1] if len(free_times) >= position else None

        return {
            "queueSize": queue_size,
            "immediate": immediate,
            "projectedAt": max(now, projected_at) if projected_at is not None else None,
            "projectedWaitMs": max(0, projected_at - now) if projected_at is not None else None,
        }

    def find_active_queue_entry_by_phone(self, phone: str) -> Optional[dict]:
        target = _normalize_phone(phone)
        match = next((q for q in self.queue if _normalize_phone(q.phone) == target), None)
        if match is None:
            return None
        views = self.list_queue(size=match.queue_size)
        return next(v for v in views if v["id"] == match.id)

    def join_queue(self, name: str, phone: str, party_size: int) -> dict:
        queue_size = map_party_size_to_queue_size(party_size)
        if queue_size is None:
            raise PartyTooLargeError("Party size exceeds the largest table.")

        target = _normalize_phone(phone)
        if any(_normalize_phone(q.phone) == target for q in self.queue):
            raise DuplicatePhoneError("This phone number already has an active reservation.")

        entry = QueueEntryRecord(
            id=f"q_{next(_id_seq)}_{_now_ms()}",
            name=name.strip(),
            phone=phone.strip(),
            party_size=party_size,
            queue_size=queue_size,
        )
        self.queue.append(entry)
        return {
            "id": entry.id,
            "name": entry.name,
            "phone": entry.phone,
            "partySize": entry.party_size,
            "queueSize": entry.queue_size,
            "joinedAt": entry.joined_at,
        }

    def cancel_queue_entry(self, queue_entry_id: str) -> None:
        before = len(self.queue)
        self.queue = [q for q in self.queue if q.id != queue_entry_id]
        if len(self.queue) == before:
            raise NotFoundError("Queue entry not found.")

    def dismiss_queue_entry(self, queue_entry_id: str) -> None:
        # Same effect as cancel_queue_entry; kept distinct since it's a
        # separate Host action (no-show) rather than a customer action.
        before = len(self.queue)
        self.queue = [q for q in self.queue if q.id != queue_entry_id]
        if len(self.queue) == before:
            raise NotFoundError("Queue entry not found.")
