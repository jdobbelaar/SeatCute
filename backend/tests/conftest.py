import pytest
from fastapi.testclient import TestClient

from seatcute_backend.db import make_engine
from seatcute_backend.deps import get_store
from seatcute_backend.main import app
from seatcute_backend.sql_store import SqlAlchemyStore


@pytest.fixture
def store() -> SqlAlchemyStore:
    """A fresh in-memory-SQLite-backed store per test, so tests never see
    each other's state."""
    return SqlAlchemyStore(make_engine("sqlite:///:memory:"))


@pytest.fixture
def client(store: SqlAlchemyStore) -> TestClient:
    app.dependency_overrides[get_store] = lambda: store
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()
