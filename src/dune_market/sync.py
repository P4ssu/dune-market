"""Local-first sync with the shared price table (a Supabase / PostgREST `observations` table).

The program always reads and writes its local SQLite database, so hover lookups stay instant and
work offline. In the background this module uploads new local rows and downloads rows other people
uploaded. Every row has a unique id, so repeating a step never duplicates anything.
"""

import logging
import threading
from datetime import datetime

import httpx

from dune_market.models import ItemKey, Observation
from dune_market.store_sqlite import SqliteStore

log = logging.getLogger(__name__)

_PULL_PAGE = 1000
_CURSOR = "pull_cursor"


def _to_row(uid: str, obs: Observation, world: str) -> dict:
    return {
        "uid": uid, "world": world, "name": obs.key.name, "category": obs.key.category, "grade": obs.key.grade,
        "kind": obs.kind, "observed_at": obs.observed_at.isoformat(), "contributor": obs.contributor,
        "avg": obs.avg, "low": obs.low, "price": obs.price, "expires_in_s": obs.expires_in_s,
    }


def _from_row(row: dict) -> tuple[str, Observation]:
    obs = Observation(
        ItemKey(row["name"], row["category"], row["grade"]), row["kind"], datetime.fromisoformat(row["observed_at"]),
        row["contributor"], avg=row.get("avg"), low=row.get("low"), price=row.get("price"),
        expires_in_s=row.get("expires_in_s"),
    )
    return row["uid"], obs


class SyncClient:
    def __init__(self, url: str, key: str, world: str, store: SqliteStore, client: httpx.Client | None = None):
        self._endpoint = url.rstrip("/") + "/rest/v1/observations"
        self._world = world
        self._store = store
        self._client = client or httpx.Client(timeout=15)
        self._headers = {"apikey": key, "Authorization": f"Bearer {key}", "Content-Type": "application/json"}
        self.batch_size = 500
        self.last_error: str | None = None

    def push(self) -> int:
        """Upload rows not yet sent; returns how many were sent."""
        sent = 0
        while True:
            batch = self._store.unsent(self.batch_size)
            if not batch:
                return sent
            response = self._client.post(
                self._endpoint,
                params={"on_conflict": "uid"},
                headers={**self._headers, "Prefer": "resolution=ignore-duplicates,return=minimal"},
                json=[_to_row(uid, obs, self._world) for uid, obs in batch],
            )
            response.raise_for_status()
            self._store.mark_sent([uid for uid, _ in batch])
            sent += len(batch)

    def pull(self) -> int:
        """Download rows other people uploaded since the last pull; returns how many were new here."""
        added = 0
        while True:
            params = {"world": f"eq.{self._world}", "order": "created_at.asc", "limit": str(_PULL_PAGE)}
            cursor = self._store.get_meta(_CURSOR)
            if cursor:
                params["created_at"] = f"gt.{cursor}"
            response = self._client.get(self._endpoint, params=params, headers=self._headers)
            response.raise_for_status()
            rows = response.json()
            if not rows:
                return added
            added += self._store.insert_remote([_from_row(r) for r in rows])
            self._store.set_meta(_CURSOR, rows[-1]["created_at"])
            if len(rows) < _PULL_PAGE:
                return added

    def sync_once(self) -> tuple[int, int] | None:
        """Push then pull. Returns (sent, new) or None if the network or the server failed (retried later)."""
        try:
            result = self.push(), self.pull()
            self.last_error = None
            return result
        except httpx.HTTPStatusError as error:
            self.last_error = f"server answered {error.response.status_code}"
        except httpx.HTTPError as error:
            self.last_error = f"network problem: {error.__class__.__name__}"
        log.warning("sync failed (%s); will retry", self.last_error)
        return None


def start_sync_thread(client: SyncClient, interval_s: float = 30.0, stop: threading.Event | None = None) -> threading.Thread:
    """Sync in the background every `interval_s` seconds."""
    stop = stop or threading.Event()

    def loop() -> None:
        while not stop.is_set():
            result = client.sync_once()
            if result and any(result):
                log.info("synced: %s sent, %s new from friends", *result)
            stop.wait(interval_s)

    thread = threading.Thread(target=loop, daemon=True, name="sync")
    thread.start()
    return thread
