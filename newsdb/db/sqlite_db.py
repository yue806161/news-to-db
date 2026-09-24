"""SQLite storage backend for parsed ProQuest news records."""
from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from pathlib import Path

# Content columns stored in the `news` table, in insertion order.
COLUMNS = [
    "proquest_id",
    "publication_title",
    "title",
    "publication_date",
    "section",
    "url",
    "abstract",
    "full_text",
    "author",
]

# created_at: UTC time the row was first written to this database. It is
# set on insert only and never overwritten when a record is re-imported.
_CREATE_NEWS_SQL = f"""
CREATE TABLE IF NOT EXISTS news (
    {", ".join(f"{c} TEXT" for c in COLUMNS if c != "proquest_id")},
    created_at TEXT,
    proquest_id TEXT PRIMARY KEY
)
"""

_UPSERT_NEWS_SQL = f"""
INSERT INTO news ({", ".join(COLUMNS)}, created_at)
VALUES ({", ".join("?" for _ in COLUMNS)}, ?)
ON CONFLICT(proquest_id) DO UPDATE SET
    {", ".join(f"{c}=excluded.{c}" for c in COLUMNS if c != "proquest_id")},
    created_at=COALESCE(news.created_at, excluded.created_at)
"""


class SQLiteNewsDB:
    """Thin wrapper around a sqlite3 connection for the `news` table."""

    def __init__(self, path: str | Path = "data/sqlite/news.db"):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(self.path)
        self._create_schema()

    def _create_schema(self) -> None:
        self.conn.execute(_CREATE_NEWS_SQL)
        # Add columns introduced after a database file was first created.
        existing = {row[1] for row in self.conn.execute("PRAGMA table_info(news)")}
        for column in [*COLUMNS, "created_at"]:
            if column not in existing:
                self.conn.execute(f"ALTER TABLE news ADD COLUMN {column} TEXT")
        self.conn.commit()

    @staticmethod
    def _row_for(record: dict) -> tuple:
        url = record.get("document_url") or record.get("docview_url")
        values = {**record, "url": url}
        return tuple(values.get(col) for col in COLUMNS)

    def upsert_records(self, records: list[dict]) -> int:
        """Insert or update article content, keyed by proquest_id."""
        now = datetime.now(timezone.utc).isoformat(timespec="seconds")
        rows = [(*self._row_for(r), now) for r in records if r.get("proquest_id")]
        self.conn.executemany(_UPSERT_NEWS_SQL, rows)
        self.conn.commit()
        return len(rows)

    def count(self) -> int:
        return self.conn.execute("SELECT COUNT(*) FROM news").fetchone()[0]

    def close(self) -> None:
        self.conn.close()

    def __enter__(self) -> "SQLiteNewsDB":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()
