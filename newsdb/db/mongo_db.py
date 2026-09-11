"""MongoDB storage backend for parsed ProQuest news records."""
from __future__ import annotations

import os

from pymongo import MongoClient, ReplaceOne
from pymongo.errors import PyMongoError

# Content fields stored per document, mirroring newsdb.db.sqlite_db.COLUMNS.
FIELDS = [
    "publication_title",
    "title",
    "publication_date",
    "url",
    "abstract",
    "full_text",
    "author",
]


class MongoNewsDB:
    """Thin wrapper around a pymongo collection for news records.

    Connection string defaults to $MONGODB_URI, falling back to a local
    mongod instance. Records are upserted keyed by proquest_id (used as _id).
    """

    def __init__(
        self,
        uri: str | None = None,
        db_name: str = "news_to_db",
        collection_name: str = "news",
        server_selection_timeout_ms: int = 5000,
    ):
        self.uri = uri or os.environ.get("MONGODB_URI", "mongodb://localhost:27017")
        self.client = MongoClient(self.uri, serverSelectionTimeoutMS=server_selection_timeout_ms)
        self.db = self.client[db_name]
        self.collection = self.db[collection_name]

    def ping(self) -> bool:
        try:
            self.client.admin.command("ping")
            return True
        except PyMongoError:
            return False

    def ensure_indexes(self) -> None:
        self.collection.create_index("proquest_id", unique=True)

    def upsert_records(self, records: list[dict]) -> int:
        """Insert or update records keyed by proquest_id. Returns count written."""
        operations = []
        for record in records:
            proquest_id = record.get("proquest_id")
            if not proquest_id:
                continue
            doc = {field: record.get(field) for field in FIELDS}
            doc["url"] = record.get("document_url") or record.get("docview_url")
            doc["_id"] = proquest_id
            operations.append(ReplaceOne({"_id": proquest_id}, doc, upsert=True))
        if not operations:
            return 0
        result = self.collection.bulk_write(operations)
        return result.upserted_count + result.modified_count

    def count(self) -> int:
        return self.collection.count_documents({})

    def close(self) -> None:
        self.client.close()

    def __enter__(self) -> "MongoNewsDB":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()
