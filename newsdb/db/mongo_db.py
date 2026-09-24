"""MongoDB storage backend for parsed ProQuest news records."""
from __future__ import annotations

import os
from datetime import datetime, timezone

from pymongo import MongoClient, UpdateOne
from pymongo.errors import PyMongoError

# Content fields stored per document, mirroring newsdb.db.sqlite_db.COLUMNS.
FIELDS = [
    "publication_title",
    "title",
    "publication_date",
    "section",
    "url",
    "abstract",
    "full_text",
    "author",
]


class MongoNewsDB:
    """Thin wrapper around a pymongo database holding one collection per source.

    Connection string defaults to $MONGODB_URI, falling back to a local
    mongod instance. Records are upserted keyed by proquest_id (used as _id).
    No indexes are created: _id is already unique, and the target
    collections live on a shared server.
    """

    def __init__(
        self,
        uri: str | None = None,
        db_name: str = "115_Text_Project",
        server_selection_timeout_ms: int = 5000,
    ):
        self.uri = uri or os.environ.get("MONGODB_URI", "mongodb://localhost:27017")
        self.client = MongoClient(self.uri, serverSelectionTimeoutMS=server_selection_timeout_ms)
        self.db = self.client[db_name]

    def ping(self) -> bool:
        try:
            self.client.admin.command("ping")
            return True
        except PyMongoError:
            return False

    def upsert_records(self, records: list[dict], collection: str) -> int:
        """Insert or update records in `collection`, keyed by proquest_id."""
        now = datetime.now(timezone.utc).isoformat(timespec="seconds")
        operations = []
        for record in records:
            proquest_id = record.get("proquest_id")
            if not proquest_id:
                continue
            doc = {field: record.get(field) for field in FIELDS}
            doc["url"] = record.get("document_url") or record.get("docview_url")
            doc["proquest_id"] = proquest_id
            # created_at is set only when the document is first inserted.
            operations.append(
                UpdateOne(
                    {"_id": proquest_id},
                    {"$set": doc, "$setOnInsert": {"created_at": now}},
                    upsert=True,
                )
            )
        if not operations:
            return 0
        result = self.db[collection].bulk_write(operations)
        return result.upserted_count + result.modified_count

    def count(self, collection: str) -> int:
        return self.db[collection].count_documents({})

    def close(self) -> None:
        self.client.close()

    def __enter__(self) -> "MongoNewsDB":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()
