"""Regression test for a real bug hit on a fresh backend restart: the first
requests to arrive concurrently (e.g. the Host page's Promise.all([listTables(),
listQueue()]) right after startup) could race inside get_store()'s singleton
construction, with two threads both missing the cache and both calling
SqlAlchemyStore.__init__ -> Base.metadata.create_all() on the same SQLite
file at once -- one of them losing the race with "table config already
exists" (sqlite3.OperationalError), surfaced to the client as a 500.
"""

import threading
from concurrent.futures import ThreadPoolExecutor

import pytest

from seatcute_backend import deps


@pytest.fixture
def fresh_singleton(tmp_path, monkeypatch):
    """Point get_store() at a brand-new on-disk database and make sure its
    singleton hasn't been constructed yet, so calling it is a genuine
    "cold start" like the real first requests after a restart."""
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'concurrent.db'}")
    deps._store = None
    yield
    deps._store = None


def test_concurrent_cold_start_calls_to_get_store_do_not_race(fresh_singleton):
    thread_count = 8
    barrier = threading.Barrier(thread_count)

    def call_get_store(_):
        barrier.wait()  # line every thread up to hit get_store() at once
        return deps.get_store()

    with ThreadPoolExecutor(max_workers=thread_count) as pool:
        stores = list(pool.map(call_get_store, range(thread_count)))

    # All concurrent callers must get the exact same store instance, and the
    # store must actually be usable (proves create_all/seeding completed
    # exactly once, not zero or twice).
    assert all(s is stores[0] for s in stores)
    assert stores[0].get_config()["counts"] == {"1": 2, "2": 4, "4": 3, "6": 1}
