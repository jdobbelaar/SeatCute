import pytest
from fastapi.testclient import TestClient

from seatcute_backend.deps import get_store
from seatcute_backend.main import app
from seatcute_backend.store import MockStore


@pytest.fixture
def store() -> MockStore:
    """A fresh in-memory store per test, so tests never see each other's state."""
    return MockStore()


@pytest.fixture
def client(store: MockStore) -> TestClient:
    app.dependency_overrides[get_store] = lambda: store
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()
