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
from functools import lru_cache

from .db import make_engine
from .sql_store import SqlAlchemyStore

DEFAULT_DATABASE_URL = "sqlite:///./db.sqlite3"


@lru_cache
def _singleton() -> SqlAlchemyStore:
    database_url = os.environ.get("DATABASE_URL", DEFAULT_DATABASE_URL)
    return SqlAlchemyStore(make_engine(database_url))


def get_store() -> SqlAlchemyStore:
    return _singleton()
