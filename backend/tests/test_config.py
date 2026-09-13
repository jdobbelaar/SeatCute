"""GET/PUT /config -- US-A1 (see _docs/specs.md and openapi.yaml)."""


def test_get_config_returns_defaults(client):
    resp = client.get("/config")
    assert resp.status_code == 200
    body = resp.json()
    assert body["sizes"] == [1, 2, 4, 6]
    assert body["counts"] == {"1": 2, "2": 4, "4": 3, "6": 1}
    assert body["turnover"] == {"1": 30, "2": 45, "4": 60, "6": 90}


def test_save_config_persists_counts_and_turnover(client):
    resp = client.put(
        "/config",
        json={
            "counts": {"1": 5, "2": 4, "4": 3, "6": 1},
            "turnover": {"1": 15, "2": 45, "4": 60, "6": 90},
        },
    )
    assert resp.status_code == 200
    assert resp.json()["counts"]["1"] == 5
    assert resp.json()["turnover"]["1"] == 15

    resp = client.get("/config")
    assert resp.json()["counts"]["1"] == 5
    assert resp.json()["turnover"]["1"] == 15


def test_save_config_missing_size_key_is_rejected(client):
    resp = client.put(
        "/config",
        json={
            "counts": {"1": 2, "2": 4, "4": 3},  # missing "6"
            "turnover": {"1": 30, "2": 45, "4": 60, "6": 90},
        },
    )
    assert resp.status_code == 422
    assert resp.json()["code"] == "VALIDATION_ERROR"


def test_save_config_negative_count_is_rejected(client):
    resp = client.put(
        "/config",
        json={
            "counts": {"1": -1, "2": 4, "4": 3, "6": 1},
            "turnover": {"1": 30, "2": 45, "4": 60, "6": 90},
        },
    )
    assert resp.status_code == 422


def test_increase_appends_new_available_tables_with_next_sequential_label(client):
    client.put(
        "/config",
        json={
            "counts": {"1": 3, "2": 4, "4": 3, "6": 1},
            "turnover": {"1": 30, "2": 45, "4": 60, "6": 90},
        },
    )
    tables = client.get("/tables").json()
    one_seat_labels = sorted(t["label"] for t in tables if t["size"] == 1)
    assert one_seat_labels == ["1-Seat #1", "1-Seat #2", "1-Seat #3"]


def test_decrease_removes_highest_numbered_available_table_first(client):
    client.put(
        "/config",
        json={
            "counts": {"1": 1, "2": 4, "4": 3, "6": 1},
            "turnover": {"1": 30, "2": 45, "4": 60, "6": 90},
        },
    )
    tables = client.get("/tables").json()
    one_seat = [t for t in tables if t["size"] == 1]
    assert len(one_seat) == 1
    assert one_seat[0]["label"] == "1-Seat #1"


def test_decrease_beyond_available_flags_occupied_tables_pending_removal(client):
    # Occupy both default 1-Seat tables via bypass, then shrink the size to 0:
    # both removals must fall onto occupied tables (no available tables exist).
    tables = client.get("/tables").json()
    one_seat_ids = [t["id"] for t in tables if t["size"] == 1]
    for table_id in one_seat_ids:
        r = client.post(f"/tables/{table_id}/seat-bypass")
        assert r.status_code == 200

    client.put(
        "/config",
        json={
            "counts": {"1": 0, "2": 4, "4": 3, "6": 1},
            "turnover": {"1": 30, "2": 45, "4": 60, "6": 90},
        },
    )

    tables = client.get("/tables").json()
    one_seat = [t for t in tables if t["size"] == 1]
    assert len(one_seat) == 2
    assert all(t["pendingRemoval"] for t in one_seat)
    assert all(t["status"] == "occupied" for t in one_seat)

    # Releasing a pending-removal table deletes it instead of freeing it.
    client.post(f"/tables/{one_seat[0]['id']}/release")
    tables = client.get("/tables").json()
    assert len([t for t in tables if t["size"] == 1]) == 1


def test_increase_unflags_pending_removal_lowest_numbered_first(client):
    # Get 2 tables of size 1 pending removal (occupy both, shrink to 0).
    tables = client.get("/tables").json()
    one_seat_ids = sorted(
        (t["id"] for t in tables if t["size"] == 1),
        key=lambda tid: next(t["label"] for t in tables if t["id"] == tid),
    )
    for table_id in one_seat_ids:
        client.post(f"/tables/{table_id}/seat-bypass")
    client.put(
        "/config",
        json={
            "counts": {"1": 0, "2": 4, "4": 3, "6": 1},
            "turnover": {"1": 30, "2": 45, "4": 60, "6": 90},
        },
    )
    tables = client.get("/tables").json()
    assert all(t["pendingRemoval"] for t in tables if t["size"] == 1)

    # Pending-removal tables still count toward "current" (spec §4), so
    # both #1 and #2 count as 2 existing tables even though both are
    # pending. Increasing to 3 needs +1: that's satisfied by un-flagging
    # the lowest-numbered pending table (#1) rather than appending a new
    # table, leaving #2 still pending and the total table count at 2.
    client.put(
        "/config",
        json={
            "counts": {"1": 3, "2": 4, "4": 3, "6": 1},
            "turnover": {"1": 30, "2": 45, "4": 60, "6": 90},
        },
    )
    tables = client.get("/tables").json()
    one_seat = [t for t in tables if t["size"] == 1]
    assert len(one_seat) == 2  # no new table appended; the quota was absorbed by un-flagging
    unflagged = [t for t in one_seat if not t["pendingRemoval"]]
    assert len(unflagged) == 1
    assert unflagged[0]["label"] == "1-Seat #1"
    still_pending = [t for t in one_seat if t["pendingRemoval"]]
    assert still_pending == [t for t in one_seat if t["label"] == "1-Seat #2"]
