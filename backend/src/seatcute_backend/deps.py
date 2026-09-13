"""FastAPI dependency wiring for the store.

A single process-wide MockStore today; swapping in a real database later
means providing a different get_store() (e.g. backed by SQLAlchemy) without
changing any router. Tests override this dependency with a fresh store per
test (see tests/conftest.py).
"""

from .store import MockStore

_store = MockStore()


def get_store() -> MockStore:
    return _store
