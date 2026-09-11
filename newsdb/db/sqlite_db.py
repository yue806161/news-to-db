"""SQLite storage backend for parsed ProQuest news records."""
from __future__ import annotations

import sqlite3
from pathlib import Path

# Content columns stored in the `news` table, in insertion order.
COLUMNS = [
    "proquest_id",
    "publication_title",
    "title",
    "publication_date",
    "url",
    "abstract",
    "full_text",
    "author",
]

_CREATE_NEWS_SQL = f"""
CREATE TABLE IF NOT EXISTS news (
    {", ".join(f"{c} TEXT" for c in COLUMNS if c != "proquest_id")},
    proquest_id TEXT PRIMARY KEY
)
"""

_UPSERT_NEWS_SQL = f"""
INSERT INTO news ({", ".join(COLUMNS)})
VALUES ({", ".join("?" for _ in COLUMNS)})
ON CONFLICT(proquest_id) DO UPDATE SET
    {", ".join(f"{c}=excluded.{c}" for c in COLUMNS if c != "proquest_id")}
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
        self.conn.commit()

    @staticmethod
    def _row_for(record: dict) -> tuple:
        url = record.get("document_url") or record.get("docview_url")
        values = {**record, "url": url}
        return tuple(values.get(col) for col in COLUMNS)

    def upsert_records(self, records: list[dict]) -> int:
        """Insert or update article content, keyed by proquest_id."""
        rows = [self._row_for(r) for r in records if r.get("proquest_id")]
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
