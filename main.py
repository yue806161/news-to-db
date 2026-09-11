"""Parse a ProQuest news export .txt file and load it into SQLite (and
optionally MongoDB).

Usage:
    python main.py news/ProQuestDocuments-2026-09-10.txt
    python main.py news/ProQuestDocuments-2026-09-10.txt --with-mongo
"""
from __future__ import annotations

import argparse
import sys

from newsdb.db.sqlite_db import SQLiteNewsDB
from newsdb.parser import parse_file


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", help="Path to a ProQuest export .txt file")
    parser.add_argument(
        "--sqlite-path", default="data/sqlite/news.db", help="Output SQLite database path"
    )
    parser.add_argument(
        "--with-mongo", action="store_true", help="Also upsert records into MongoDB"
    )
    parser.add_argument(
        "--mongo-uri", default=None, help="MongoDB URI (defaults to $MONGODB_URI or localhost)"
    )
    args = parser.parse_args()

    print(f"Parsing {args.input} ...")
    records = parse_file(args.input)
    print(f"Parsed {len(records)} news records")

    with SQLiteNewsDB(args.sqlite_path) as db:
        written = db.upsert_records(records)
        total = db.count()
    print(f"SQLite: upserted {written} records into {args.sqlite_path} (table now has {total} rows)")

    if args.with_mongo:
        from newsdb.db.mongo_db import MongoNewsDB

        with MongoNewsDB(uri=args.mongo_uri) as mdb:
            if not mdb.ping():
                print(f"MongoDB: could not reach {mdb.uri}, skipping Mongo write", file=sys.stderr)
                return 1
            mdb.ensure_indexes()
            written = mdb.upsert_records(records)
            total = mdb.count()
        print(f"MongoDB: upserted {written} records (collection now has {total} documents)")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
