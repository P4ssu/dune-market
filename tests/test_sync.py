"""Local-first sync with a shared PostgREST (Supabase) table, against an in-memory fake server."""

import json
from datetime import datetime, timedelta, timezone

import httpx

from dune_market.models import ItemKey, Observation
from dune_market.store_sqlite import SqliteStore
from dune_market.sync import SyncClient

NOW = datetime(2026, 10, 19, 12, 0, tzinfo=timezone.utc)
KEY = ItemKey("Cobalt Paste", "MISC - REFINEDRESOURCES", "unknown")
URL = "https://example.supabase.co"


class FakeSupabase:
    """Just enough of PostgREST: insert with ignore-duplicates, filtered/ordered/limited select."""

    def __init__(self, key="secret"):
        self.key, self.rows, self.requests, self.down = key, [], [], False

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        if self.down:
            raise httpx.ConnectError("no network")
        if request.headers.get("apikey") != self.key or request.headers.get("authorization") != f"Bearer {self.key}":
            return httpx.Response(401, json={"message": "bad key"})
        if request.method == "POST":
            for row in json.loads(request.content):
                if not any(r["uid"] == row["uid"] for r in self.rows):
                    row["created_at"] = f"2026-10-19T12:00:{len(self.rows):02d}+00:00"
                    self.rows.append(row)
            return httpx.Response(201)
        params = request.url.params
        rows = [r for r in self.rows if r["world"] == params["world"].removeprefix("eq.")]
        if "created_at" in params:
            rows = [r for r in rows if r["created_at"] > params["created_at"].removeprefix("gt.")]
        rows.sort(key=lambda r: r["created_at"])
        return httpx.Response(200, json=rows[: int(params.get("limit", 1000))])


def make(tmp_path, name, server, world="Andromeda", contributor="Mari"):
    store = SqliteStore(str(tmp_path / f"{name}.db"))
    client = httpx.Client(transport=httpx.MockTransport(server))
    return store, SyncClient(URL, server.key, world, store, client=client), contributor


def sell(avg, low, contributor="Mari", hours_ago=1, key=KEY):
    return Observation(key, "sell", NOW - timedelta(hours=hours_ago), contributor, avg=avg, low=low)


def test_push_uploads_unsent_rows_once(tmp_path):
    server = FakeSupabase()
    store, sync, _ = make(tmp_path, "a", server)
    store.add([sell(100, 80), sell(110, 90, hours_ago=0)])
    assert sync.push() == 2
    assert len(server.rows) == 2 and {r["world"] for r in server.rows} == {"Andromeda"}
    assert sync.push() == 0  # nothing left to send
    assert len(server.rows) == 2


def test_push_is_idempotent_if_the_response_was_lost(tmp_path):
    server = FakeSupabase()
    store, sync, _ = make(tmp_path, "a", server)
    store.add([sell(100, 80)])
    sync.push()
    store._connect().execute("UPDATE observations SET synced = 0").connection.commit()  # pretend we never heard back
    sync.push()
    assert len(server.rows) == 1  # the server ignored the duplicate uid


def test_requests_carry_the_shared_key(tmp_path):
    server = FakeSupabase(key="friend-key")
    store, sync, _ = make(tmp_path, "a", server)
    store.add([sell(100, 80)])
    sync.sync_once()
    assert all(r.headers["apikey"] == "friend-key" and r.headers["authorization"] == "Bearer friend-key" for r in server.requests)


def test_pull_brings_in_friends_rows_and_lookup_sees_them(tmp_path):
    server = FakeSupabase()
    a, sync_a, _ = make(tmp_path, "a", server)
    b, sync_b, _ = make(tmp_path, "b", server)
    a.add([sell(100, 80, contributor="Mari")])
    sync_a.sync_once()
    assert sync_b.pull() == 1
    (stats,) = b.lookup("Cobalt Paste", "MISC - REFINEDRESOURCES", NOW)
    assert (stats.avg, stats.contributor) == (100, "Mari")


def test_pull_does_not_duplicate_my_own_rows_and_only_fetches_new_ones(tmp_path):
    server = FakeSupabase()
    a, sync_a, _ = make(tmp_path, "a", server)
    a.add([sell(100, 80)])
    sync_a.sync_once()  # pushes, then pulls its own row back
    count = a._connect().execute("SELECT COUNT(*) FROM observations").fetchone()[0]
    assert count == 1
    assert sync_a.pull() == 0  # the cursor moved past everything already seen
    other, sync_o, _ = make(tmp_path, "o", server)
    other.add([sell(120, 95, contributor="Jaan", hours_ago=0)])
    sync_o.push()
    assert sync_a.pull() == 1


def test_pulled_rows_are_not_uploaded_again(tmp_path):
    server = FakeSupabase()
    a, sync_a, _ = make(tmp_path, "a", server)
    b, sync_b, _ = make(tmp_path, "b", server)
    a.add([sell(100, 80)])
    sync_a.sync_once()
    sync_b.sync_once()
    assert len(server.rows) == 1
    assert sync_b.push() == 0


def test_other_worlds_are_not_pulled(tmp_path):
    server = FakeSupabase()
    a, sync_a, _ = make(tmp_path, "a", server, world="Andromeda")
    c, sync_c, _ = make(tmp_path, "c", server, world="Orion")
    c.add([sell(999, 900, contributor="Stranger")])
    sync_c.sync_once()
    sync_a.sync_once()
    assert a.lookup("Cobalt Paste", "MISC - REFINEDRESOURCES", NOW) == []


def test_network_failure_keeps_rows_for_the_next_try(tmp_path):
    server = FakeSupabase()
    store, sync, _ = make(tmp_path, "a", server)
    store.add([sell(100, 80)])
    server.down = True
    assert sync.sync_once() is None  # no exception, just "not synced"
    server.down = False
    assert sync.sync_once() == (1, 0)  # pushed one; its own row coming back is not new here
    assert len(server.rows) == 1


def test_wrong_key_is_reported_not_raised(tmp_path):
    server = FakeSupabase(key="right")
    store = SqliteStore(str(tmp_path / "a.db"))
    sync = SyncClient(URL, "wrong", "Andromeda", store, client=httpx.Client(transport=httpx.MockTransport(server)))
    store.add([sell(100, 80)])
    assert sync.sync_once() is None
    assert sync.last_error and "401" in sync.last_error


def test_old_local_database_gets_ids_and_is_uploaded(tmp_path):
    import sqlite3

    path = str(tmp_path / "old.db")
    db = sqlite3.connect(path)
    db.execute(
        "CREATE TABLE observations (name TEXT NOT NULL, category TEXT NOT NULL, grade TEXT NOT NULL, kind TEXT NOT NULL,"
        " observed_at TEXT NOT NULL, contributor TEXT NOT NULL, avg INTEGER, low INTEGER, price INTEGER, expires_in_s INTEGER)"
    )
    db.execute("INSERT INTO observations VALUES ('Cobalt Paste','MISC - REFINEDRESOURCES','unknown','sell',?,'Mari',100,80,NULL,NULL)",
               (NOW.isoformat(),))
    db.execute("INSERT INTO observations VALUES ('Spice Sand','MISC - RESOURCES','unknown','sell',?,'Mari',50,40,NULL,NULL)",
               (NOW.isoformat(),))
    db.commit()
    db.close()
    server = FakeSupabase()
    store = SqliteStore(path)
    sync = SyncClient(URL, server.key, "Andromeda", store, client=httpx.Client(transport=httpx.MockTransport(server)))
    assert sync.push() == 2
    assert len({r["uid"] for r in server.rows}) == 2


def test_push_sends_batches(tmp_path):
    server = FakeSupabase()
    store, sync, _ = make(tmp_path, "a", server)
    sync.batch_size = 3
    store.add([sell(100 + i, 80, hours_ago=i) for i in range(7)])
    assert sync.push() == 7
    posts = [r for r in server.requests if r.method == "POST"]
    assert [len(json.loads(r.content)) for r in posts] == [3, 3, 1]
