"""Local SQLite price store (also the local cache of the shared database)."""

import sqlite3
import uuid
from datetime import datetime

from dune_market.models import ItemKey, ItemStats, Observation
from dune_market.ocr import name_key
from dune_market.stats import stats_by_grade

_SCHEMA = """
CREATE TABLE IF NOT EXISTS observations (
    name TEXT NOT NULL,
    category TEXT NOT NULL,
    grade TEXT NOT NULL,
    kind TEXT NOT NULL,
    observed_at TEXT NOT NULL,
    contributor TEXT NOT NULL,
    avg INTEGER,
    low INTEGER,
    price INTEGER,
    expires_in_s INTEGER,
    name_key TEXT NOT NULL DEFAULT '',
    uid TEXT,
    synced INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT NOT NULL);
"""

_COLUMNS = "name, category, grade, kind, observed_at, contributor, avg, low, price, expires_in_s"
_INSERT_COLUMNS = _COLUMNS + ", name_key, uid, synced"


def _to_observation(row: tuple) -> Observation:
    name, category, grade, kind, observed_at, contributor, avg, low, price, expires = row[:10]
    return Observation(
        ItemKey(name, category, grade), kind, datetime.fromisoformat(observed_at),
        contributor, avg=avg, low=low, price=price, expires_in_s=expires,
    )


def _values(o: Observation, uid: str, synced: int) -> tuple:
    return (o.key.name, o.key.category, o.key.grade, o.kind, o.observed_at.isoformat(), o.contributor,
            o.avg, o.low, o.price, o.expires_in_s, name_key(o.key.name), uid, synced)


class SqliteStore:
    def __init__(self, path: str):
        self._path = path
        with self._connect() as db:
            db.executescript(_SCHEMA)
            self._migrate(db)

    @staticmethod
    def _migrate(db: sqlite3.Connection) -> None:
        columns = {row[1] for row in db.execute("PRAGMA table_info(observations)")}
        # Databases written by earlier versions lack these columns.
        if "name_key" not in columns:
            db.execute("ALTER TABLE observations ADD COLUMN name_key TEXT NOT NULL DEFAULT ''")
        if "uid" not in columns:
            db.execute("ALTER TABLE observations ADD COLUMN uid TEXT")
        if "synced" not in columns:
            db.execute("ALTER TABLE observations ADD COLUMN synced INTEGER NOT NULL DEFAULT 0")
        for (name,) in db.execute("SELECT DISTINCT name FROM observations WHERE name_key = ''").fetchall():
            db.execute("UPDATE observations SET name_key = ? WHERE name = ? AND name_key = ''", (name_key(name), name))
        for (rowid,) in db.execute("SELECT rowid FROM observations WHERE uid IS NULL").fetchall():
            db.execute("UPDATE observations SET uid = ? WHERE rowid = ?", (uuid.uuid4().hex, rowid))
        db.execute("CREATE INDEX IF NOT EXISTS idx_observations_item ON observations (name_key, category)")
        db.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_observations_uid ON observations (uid)")

    def _connect(self) -> sqlite3.Connection:
        # A connection per call keeps the store usable from the scanner, overlay and sync threads.
        return sqlite3.connect(self._path)

    def add(self, observations: list[Observation]) -> None:
        rows = [_values(o, uuid.uuid4().hex, 0) for o in observations]
        with self._connect() as db:
            db.executemany(f"INSERT INTO observations ({_INSERT_COLUMNS}) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)", rows)

    def latest_sell(self, key: ItemKey) -> Observation | None:
        with self._connect() as db:
            row = db.execute(
                f"SELECT {_COLUMNS} FROM observations WHERE name_key=? AND category=? AND grade=? "
                "AND kind='sell' ORDER BY observed_at DESC LIMIT 1",
                (name_key(key.name), key.category, key.grade),
            ).fetchone()
        return _to_observation(row) if row else None

    def lookup(self, name: str, category: str, now: datetime) -> list[ItemStats]:
        with self._connect() as db:
            rows = db.execute(
                f"SELECT {_COLUMNS} FROM observations WHERE name_key=? AND category=?", (name_key(name), category)
            ).fetchall()
        return stats_by_grade([_to_observation(r) for r in rows], now)

    # --- sync with the shared database -------------------------------------------------------

    def unsent(self, limit: int) -> list[tuple[str, Observation]]:
        """Rows not yet uploaded, as (uid, observation)."""
        with self._connect() as db:
            rows = db.execute(
                f"SELECT {_COLUMNS}, uid FROM observations WHERE synced = 0 ORDER BY observed_at LIMIT ?", (limit,)
            ).fetchall()
        return [(row[10], _to_observation(row)) for row in rows]

    def mark_sent(self, uids: list[str]) -> None:
        with self._connect() as db:
            db.executemany("UPDATE observations SET synced = 1 WHERE uid = ?", [(u,) for u in uids])

    def insert_remote(self, rows: list[tuple[str, Observation]]) -> int:
        """Add rows that came from the shared database (already synced); returns how many were new."""
        added = 0
        with self._connect() as db:
            for uid, obs in rows:
                cursor = db.execute(
                    f"INSERT OR IGNORE INTO observations ({_INSERT_COLUMNS}) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
                    _values(obs, uid, 1),
                )
                added += cursor.rowcount
        return added

    def get_meta(self, key: str) -> str | None:
        with self._connect() as db:
            row = db.execute("SELECT value FROM meta WHERE key = ?", (key,)).fetchone()
        return row[0] if row else None

    def set_meta(self, key: str, value: str) -> None:
        with self._connect() as db:
            db.execute("INSERT INTO meta (key, value) VALUES (?, ?) ON CONFLICT(key) DO UPDATE SET value = excluded.value", (key, value))
