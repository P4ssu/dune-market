"""Local SQLite price store."""

import sqlite3
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
    name_key TEXT NOT NULL DEFAULT ''
);
"""

_COLUMNS = "name, category, grade, kind, observed_at, contributor, avg, low, price, expires_in_s"
_INSERT_COLUMNS = _COLUMNS + ", name_key"


def _to_observation(row: tuple) -> Observation:
    name, category, grade, kind, observed_at, contributor, avg, low, price, expires = row
    return Observation(
        ItemKey(name, category, grade), kind, datetime.fromisoformat(observed_at),
        contributor, avg=avg, low=low, price=price, expires_in_s=expires,
    )


class SqliteStore:
    def __init__(self, path: str):
        self._path = path
        with self._connect() as db:
            db.executescript(_SCHEMA)
            self._migrate(db)

    @staticmethod
    def _migrate(db: sqlite3.Connection) -> None:
        columns = {row[1] for row in db.execute("PRAGMA table_info(observations)")}
        if "name_key" not in columns:  # database written by an earlier version
            db.execute("ALTER TABLE observations ADD COLUMN name_key TEXT NOT NULL DEFAULT ''")
        for (name,) in db.execute("SELECT DISTINCT name FROM observations WHERE name_key = ''").fetchall():
            db.execute("UPDATE observations SET name_key = ? WHERE name = ? AND name_key = ''", (name_key(name), name))
        db.execute("CREATE INDEX IF NOT EXISTS idx_observations_item ON observations (name_key, category)")

    def _connect(self) -> sqlite3.Connection:
        # A connection per call keeps the store usable from the scanner and overlay threads.
        return sqlite3.connect(self._path)

    def add(self, observations: list[Observation]) -> None:
        rows = [
            (o.key.name, o.key.category, o.key.grade, o.kind, o.observed_at.isoformat(),
             o.contributor, o.avg, o.low, o.price, o.expires_in_s, name_key(o.key.name))
            for o in observations
        ]
        with self._connect() as db:
            db.executemany(f"INSERT INTO observations ({_INSERT_COLUMNS}) VALUES (?,?,?,?,?,?,?,?,?,?,?)", rows)

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
