"""GET /tables and the table-transaction endpoints -- US-H1, US-H2, US-H3."""


def test_list_tables_seeds_default_counts_per_size(client):
    tables = client.get("/tables").json()
    counts = {}
    for t in tables:
        counts[t["size"]] = counts.get(t["size"], 0) + 1
    assert counts == {1: 2, 2: 4, 4: 3, 6: 1}
    assert all(t["status"] == "available" for t in tables)
    assert all(t["occupiedAt"] is None for t in tables)
    assert all(t["party"] is None for t in tables)
    assert all(t["pendingRemoval"] is False for t in tables)
    assert all(t["elapsedMinutes"] is None for t in tables)
    assert all(isinstance(t["freeAt"], int) for t in tables)


def _first_available(client, size):
    tables = client.get("/tables").json()
    return next(t for t in tables if t["size"] == size and t["status"] == "available")


def test_seat_bypass_occupies_table_with_no_party(client):
    table = _first_available(client, 2)
    resp = client.post(f"/tables/{table['id']}/seat-bypass")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "occupied"
    assert body["party"] is None
    assert isinstance(body["occupiedAt"], int)


def test_seat_bypass_on_occupied_table_is_rejected(client):
    table = _first_available(client, 2)
    client.post(f"/tables/{table['id']}/seat-bypass")
    resp = client.post(f"/tables/{table['id']}/seat-bypass")
    assert resp.status_code == 409
    assert resp.json()["code"] == "TABLE_UNAVAILABLE"


def test_seat_bypass_unknown_table_404s(client):
    resp = client.post("/tables/does-not-exist/seat-bypass")
    assert resp.status_code == 404
    assert resp.json()["code"] == "NOT_FOUND"


def test_seat_from_queue_attaches_party_and_removes_entry(client):
    join = client.post(
        "/queue", json={"name": "Alice", "phone": "555-1234", "partySize": 2}
    ).json()
    table = _first_available(client, 2)

    resp = client.post(
        f"/tables/{table['id']}/seat-from-queue",
        json={"queueEntryId": join["id"]},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "occupied"
    assert body["party"] == {"name": "Alice", "phone": "555-1234"}

    assert client.get("/queue").json() == []


def test_seat_from_queue_unknown_entry_404s(client):
    table = _first_available(client, 2)
    resp = client.post(
        f"/tables/{table['id']}/seat-from-queue",
        json={"queueEntryId": "does-not-exist"},
    )
    assert resp.status_code == 404
    assert resp.json()["code"] == "NOT_FOUND"


def test_seat_from_queue_on_occupied_table_is_rejected(client):
    join = client.post(
        "/queue", json={"name": "Alice", "phone": "555-1234", "partySize": 2}
    ).json()
    table = _first_available(client, 2)
    client.post(f"/tables/{table['id']}/seat-bypass")

    resp = client.post(
        f"/tables/{table['id']}/seat-from-queue",
        json={"queueEntryId": join["id"]},
    )
    assert resp.status_code == 409
    assert resp.json()["code"] == "TABLE_UNAVAILABLE"


def test_release_frees_a_normal_occupied_table(client):
    table = _first_available(client, 2)
    client.post(f"/tables/{table['id']}/seat-bypass")

    resp = client.post(f"/tables/{table['id']}/release")
    assert resp.status_code == 204

    refreshed = next(t for t in client.get("/tables").json() if t["id"] == table["id"])
    assert refreshed["status"] == "available"
    assert refreshed["occupiedAt"] is None
    assert refreshed["party"] is None


def test_release_unknown_table_404s(client):
    resp = client.post("/tables/does-not-exist/release")
    assert resp.status_code == 404


def test_release_does_not_auto_seat_the_next_queue_entry(client):
    client.post("/queue", json={"name": "Bob", "phone": "555-9999", "partySize": 2})
    table = _first_available(client, 2)
    client.post(f"/tables/{table['id']}/seat-bypass")
    client.post(f"/tables/{table['id']}/release")

    assert len(client.get("/queue").json()) == 1
