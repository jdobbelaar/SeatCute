"""Queue + wait-estimate endpoints -- US-H4, US-H5, US-K1, US-K2, US-K3."""


def _occupy_all(client, size):
    tables = client.get("/tables").json()
    for t in tables:
        if t["size"] == size and t["status"] == "available":
            client.post(f"/tables/{t['id']}/seat-bypass")


def test_join_queue_maps_party_size_to_smallest_sufficient_queue_size(client):
    resp = client.post(
        "/queue", json={"name": "Alice", "phone": "555-1111", "partySize": 3}
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["queueSize"] == 4
    assert body["partySize"] == 3
    assert "id" in body and "joinedAt" in body


def test_join_queue_party_over_six_is_rejected(client):
    resp = client.post(
        "/queue", json={"name": "Big Party", "phone": "555-2222", "partySize": 8}
    )
    assert resp.status_code == 422
    assert resp.json()["code"] == "PARTY_TOO_LARGE"
    assert client.get("/queue").json() == []


def test_join_queue_rejects_duplicate_phone_across_any_size(client):
    client.post("/queue", json={"name": "Alice", "phone": "555-3333", "partySize": 2})
    resp = client.post(
        "/queue", json={"name": "Alice Again", "phone": "555-3333", "partySize": 6}
    )
    assert resp.status_code == 409
    assert resp.json()["code"] == "DUPLICATE_PHONE"
    assert len(client.get("/queue").json()) == 1


def test_list_queue_reports_join_order_and_position(client):
    client.post("/queue", json={"name": "First", "phone": "555-0001", "partySize": 2})
    client.post("/queue", json={"name": "Second", "phone": "555-0002", "partySize": 2})

    entries = client.get("/queue", params={"size": 2}).json()
    assert [e["name"] for e in entries] == ["First", "Second"]
    assert [e["position"] for e in entries] == [1, 2]


def test_list_queue_filters_by_size(client):
    client.post("/queue", json={"name": "Two", "phone": "555-0010", "partySize": 2})
    client.post("/queue", json={"name": "Six", "phone": "555-0011", "partySize": 6})

    only_two = client.get("/queue", params={"size": 2}).json()
    assert [e["name"] for e in only_two] == ["Two"]

    everyone = client.get("/queue").json()
    assert {e["name"] for e in everyone} == {"Two", "Six"}


def test_list_queue_rejects_invalid_size(client):
    resp = client.get("/queue", params={"size": 3})
    assert resp.status_code == 400
    assert resp.json()["code"] == "VALIDATION_ERROR"


def test_list_queue_wait_accounts_for_queue_depth(client):
    # 4 size-2 tables total; occupy 3, leave 1 available.
    tables = [t for t in client.get("/tables").json() if t["size"] == 2]
    for t in tables[:3]:
        client.post(f"/tables/{t['id']}/seat-bypass")

    client.post("/queue", json={"name": "First", "phone": "555-0100", "partySize": 2})
    client.post("/queue", json={"name": "Second", "phone": "555-0101", "partySize": 2})

    entries = client.get("/queue", params={"size": 2}).json()
    first, second = entries
    # First maps onto the one still-available table: ~no wait.
    assert first["projectedWaitMs"] == 0
    # Second maps onto one of the occupied tables: a real, positive wait.
    assert second["projectedWaitMs"] > 0


def test_get_wait_estimate_immediate_when_table_free_and_queue_empty(client):
    resp = client.get("/queue/wait-estimate", params={"partySize": 1})
    assert resp.status_code == 200
    body = resp.json()
    assert body["queueSize"] == 1
    assert body["immediate"] is True


def test_get_wait_estimate_not_immediate_once_queue_is_non_empty(client):
    # Spec decision #7: a free table doesn't matter once the queue for that
    # size is non-empty -- no line-skipping.
    client.post("/queue", json={"name": "Ahead", "phone": "555-0200", "partySize": 2})
    resp = client.get("/queue/wait-estimate", params={"partySize": 2})
    body = resp.json()
    assert body["immediate"] is False
    assert isinstance(body["projectedWaitMs"], int)


def test_get_wait_estimate_over_six_returns_null_queue_size(client):
    resp = client.get("/queue/wait-estimate", params={"partySize": 10})
    body = resp.json()
    assert body["queueSize"] is None
    assert body["immediate"] is False


def test_get_wait_estimate_does_not_create_a_queue_entry(client):
    client.get("/queue/wait-estimate", params={"partySize": 2})
    assert client.get("/queue").json() == []


def test_get_wait_estimate_missing_party_size_is_rejected(client):
    resp = client.get("/queue/wait-estimate")
    assert resp.status_code == 400
    assert resp.json()["code"] == "VALIDATION_ERROR"


def test_reservation_status_found_by_phone(client):
    client.post("/queue", json={"name": "Alice", "phone": "555-0300", "partySize": 2})
    resp = client.get("/reservation-status", params={"phone": "555-0300"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["name"] == "Alice"
    assert body["position"] == 1


def test_reservation_status_not_found(client):
    resp = client.get("/reservation-status", params={"phone": "555-9999"})
    assert resp.status_code == 404
    assert resp.json()["code"] == "NOT_FOUND"


def test_cancel_queue_entry_removes_it(client):
    entry = client.post(
        "/queue", json={"name": "Alice", "phone": "555-0400", "partySize": 2}
    ).json()
    resp = client.delete(f"/queue/{entry['id']}")
    assert resp.status_code == 204
    assert client.get("/queue").json() == []


def test_cancel_unknown_queue_entry_404s(client):
    resp = client.delete("/queue/does-not-exist")
    assert resp.status_code == 404


def test_dismiss_queue_entry_removes_it_without_touching_tables(client):
    entry = client.post(
        "/queue", json={"name": "No Show", "phone": "555-0500", "partySize": 2}
    ).json()
    available_before = sum(
        1 for t in client.get("/tables").json() if t["status"] == "available"
    )

    resp = client.post(f"/queue/{entry['id']}/dismiss")
    assert resp.status_code == 204
    assert client.get("/queue").json() == []

    available_after = sum(
        1 for t in client.get("/tables").json() if t["status"] == "available"
    )
    assert available_after == available_before


def test_dismiss_unknown_queue_entry_404s(client):
    resp = client.post("/queue/does-not-exist/dismiss")
    assert resp.status_code == 404
