"""Persistence-specific behavior that a pure in-memory store couldn't
exercise: does state actually survive a process restart against the same
database file, and does reopening it stay safe (no reseeding, no duplicate
rows, no colliding labels/ids)?

Uses SqlAlchemyStore directly (not the HTTP client) since this is about the
storage layer, not routing -- and a *file-backed* SQLite DB (via tmp_path),
since :memory: can't be reopened by a second, independent engine the way a
real restart would reconnect to a real database file.
"""

from seatcute_backend.db import make_engine
from seatcute_backend.sql_store import SqlAlchemyStore


def _default_turnover():
    return {1: 30, 2: 45, 4: 60, 6: 90}


def test_state_survives_reopening_the_same_database(tmp_path):
    db_url = f"sqlite:///{tmp_path / 'restart.db'}"

    store1 = SqlAlchemyStore(make_engine(db_url))
    table = next(t for t in store1.list_tables() if t["size"] == 2 and t["status"] == "available")
    store1.seat_bypass(table["id"])
    store1.save_config({1: 2, 2: 5, 4: 3, 6: 1}, _default_turnover())

    # A brand-new store/engine pointed at the same file simulates a restart.
    store2 = SqlAlchemyStore(make_engine(db_url))

    assert store2.get_config()["counts"]["2"] == 5

    tables = store2.list_tables()
    assert len([t for t in tables if t["size"] == 2]) == 5
    reopened = next(t for t in tables if t["id"] == table["id"])
    assert reopened["status"] == "occupied"


def test_reopening_does_not_reseed_or_duplicate_tables(tmp_path):
    db_url = f"sqlite:///{tmp_path / 'reopen.db'}"

    store1 = SqlAlchemyStore(make_engine(db_url))
    initial_total = len(store1.list_tables())
    assert initial_total == 10  # 2 + 4 + 3 + 1 default seed

    store2 = SqlAlchemyStore(make_engine(db_url))
    assert len(store2.list_tables()) == initial_total

    store3 = SqlAlchemyStore(make_engine(db_url))
    assert len(store3.list_tables()) == initial_total


def test_label_counters_persist_so_new_tables_never_reuse_or_collide(tmp_path):
    db_url = f"sqlite:///{tmp_path / 'counters.db'}"

    store1 = SqlAlchemyStore(make_engine(db_url))
    store1.save_config({1: 2, 2: 5, 4: 3, 6: 1}, _default_turnover())  # adds 2-Seat #5
    labels = sorted(t["label"] for t in store1.list_tables() if t["size"] == 2)
    assert labels[-1] == "2-Seat #5"

    # Reopen (simulated restart) and increase again -- must continue from #6,
    # not restart the counter at #1 (which would collide with existing ids).
    store2 = SqlAlchemyStore(make_engine(db_url))
    store2.save_config({1: 2, 2: 6, 4: 3, 6: 1}, _default_turnover())

    size_2_tables = [t for t in store2.list_tables() if t["size"] == 2]
    assert sorted(t["label"] for t in size_2_tables)[-1] == "2-Seat #6"
    ids = [t["id"] for t in size_2_tables]
    assert len(ids) == len(set(ids))


def test_queue_entries_persist_across_reopening(tmp_path):
    db_url = f"sqlite:///{tmp_path / 'queue.db'}"

    store1 = SqlAlchemyStore(make_engine(db_url))
    store1.join_queue("Alice", "555-1234", 2)

    store2 = SqlAlchemyStore(make_engine(db_url))
    entries = store2.list_queue(size=2)
    assert len(entries) == 1
    assert entries[0]["name"] == "Alice"
