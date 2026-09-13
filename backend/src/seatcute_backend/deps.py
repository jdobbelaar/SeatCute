"""FastAPI dependency wiring for the store.

Backed by SQLAlchemy against DATABASE_URL (default: a local SQLite file
under the working directory this process was started from). Swapping to
Postgres/MySQL/etc. later is a DATABASE_URL + driver-package change --
db.py and sql_store.py contain no SQLite-specific SQL, so no router needs
to change either.

Tests override get_store with a fresh in-memory-SQLite-backed store per
test (see tests/conftest.py), so the on-disk default below is never
touched during a test run.
"""

import os
import threading

from .db import make_engine
from .sql_store import SqlAlchemyStore

DEFAULT_DATABASE_URL = "sqlite:///./db.sqlite3"

_store: SqlAlchemyStore | None = None
_store_lock = threading.Lock()


def get_store() -> SqlAlchemyStore:
    # FastAPI runs sync path operations in a threadpool, so the first
    # requests after a restart (e.g. the Host page's concurrent
    # listTables()/listQueue() calls) can call this before anything has been
    # constructed yet. Without a lock, two threads can both see `_store is
    # None`, and both then construct a SqlAlchemyStore -- each running
    # Base.metadata.create_all() on the same database at once, with one
    # losing the race ("table already exists"). Double-checked locking here
    # guarantees the store (and its create_all/seed) is built exactly once.
    global _store
    if _store is None:
        with _store_lock:
            if _store is None:
                database_url = os.environ.get("DATABASE_URL", DEFAULT_DATABASE_URL)
                _store = SqlAlchemyStore(make_engine(database_url))
    return _store
