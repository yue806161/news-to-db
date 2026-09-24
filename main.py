"""Parse ProQuest news export .txt files and load them into MongoDB and/or
SQLite (default: MongoDB).

Each input may be a single .txt file or a directory, in which case every
*.txt file under it is parsed. Records are upserted keyed by their
ProQuest document id (proquest_id), so re-running on overlapping files
(e.g. new exports whose date range overlaps an older file) is safe and
de-duplicates automatically.

Usage:
    python main.py                          # scans Data/FT and Data/WSJ
    python main.py Data/FT Data/WSJ
    python main.py "Data/FT/ProQuestDocuments-1996-*.txt"   # one year
    python main.py Data/FT/ProQuestDocuments-1996-05-31-第一頁.txt
    python main.py Data/FT --db sqlite      # SQLite instead of MongoDB
    python main.py Data/FT --db both        # write to both
"""
from __future__ import annotations

import argparse
import glob
import sys
from pathlib import Path

from newsdb.db.sqlite_db import SQLiteNewsDB
from newsdb.parser import parse_file

DEFAULT_INPUTS = ["Data/FT", "Data/WSJ"]

# Source folder name -> MongoDB collection. A file's source is the closest
# parent folder of that name, e.g. Data/FT/1996/x.txt -> FinancialTimes.
SOURCE_COLLECTIONS = {"FT": "FinancialTimes", "WSJ": "WSJ"}


def source_collection(path: Path) -> str | None:
    for part in reversed(path.parts):
        if part.upper() in SOURCE_COLLECTIONS:
            return SOURCE_COLLECTIONS[part.upper()]
    return None


def collect_txt_files(inputs: list[str]) -> list[Path]:
    """Resolve each input (file or directory) to a sorted list of .txt files."""
    files: list[Path] = []
    for raw in inputs:
        # Expand wildcards ourselves: PowerShell/cmd don't glob for programs.
        if any(ch in raw for ch in "*?["):
            matches = sorted(Path(m) for m in glob.glob(raw, recursive=True))
            if not matches:
                print(f"warning: no files match {raw}, skipping", file=sys.stderr)
            files.extend(m for m in matches if m.is_file())
            continue
        path = Path(raw)
        if path.is_dir():
            files.extend(sorted(path.rglob("*.txt")))
        elif path.is_file():
            files.append(path)
        else:
            print(f"warning: {path} not found, skipping", file=sys.stderr)
    return files


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        "inputs",
        nargs="*",
        default=DEFAULT_INPUTS,
        help=f"ProQuest export .txt file(s) or directories (default: {DEFAULT_INPUTS})",
    )
    parser.add_argument(
        "--db",
        choices=["mongo", "sqlite", "both"],
        default="mongo",
        help="Target database (default: mongo)",
    )
    parser.add_argument(
        "--sqlite-path", default="Data/sqlite/news.db", help="Output SQLite database path"
    )
    parser.add_argument(
        "--mongo-uri", default=None, help="MongoDB URI (defaults to $MONGODB_URI or localhost)"
    )
    parser.add_argument(
        "--mongo-db", default="115_Text_Project", help="MongoDB database (default: 115_Text_Project)"
    )
    args = parser.parse_args()

    txt_files = collect_txt_files(args.inputs)
    if not txt_files:
        print("No .txt files found to parse.", file=sys.stderr)
        return 1
    print(f"Found {len(txt_files)} .txt file(s)")

    records: list[dict] = []
    by_collection: dict[str, list[dict]] = {}
    unknown_source: list[Path] = []
    for path in txt_files:
        try:
            file_records = parse_file(path)
        except Exception as exc:  # noqa: BLE001 - keep ingesting the rest of the files
            print(f"warning: failed to parse {path}: {exc}", file=sys.stderr)
            continue
        print(f"  {path}: {len(file_records)} records")
        records.extend(file_records)
        collection = source_collection(path)
        if collection:
            by_collection.setdefault(collection, []).extend(file_records)
        else:
            unknown_source.append(path)

    unique_ids = {r["proquest_id"] for r in records if r.get("proquest_id")}
    print(
        f"Parsed {len(records)} records total, "
        f"{len(unique_ids)} unique by proquest_id "
        f"({len(records) - len(unique_ids)} duplicate)"
    )

    bad_dates = sorted(
        {r["publication_date_raw"] for r in records
         if r.get("publication_date_raw") and not r.get("publication_date")}
    )
    if bad_dates:
        print(
            f"warning: {len(bad_dates)} publication date format(s) could not be parsed "
            f"(raw text kept, date left empty): {bad_dates[:5]}",
            file=sys.stderr,
        )

    failed = False

    if args.db in ("mongo", "both"):
        from newsdb.db.mongo_db import MongoNewsDB

        with MongoNewsDB(uri=args.mongo_uri, db_name=args.mongo_db) as mdb:
            if not mdb.ping():
                print(f"MongoDB: could not reach {mdb.uri}, nothing written", file=sys.stderr)
                failed = True
            else:
                for collection, coll_records in sorted(by_collection.items()):
                    written = mdb.upsert_records(coll_records, collection)
                    total = mdb.count(collection)
                    print(
                        f"MongoDB {args.mongo_db}.{collection}: wrote {written} records "
                        f"(collection now has {total} documents)"
                    )
                for path in unknown_source:
                    print(
                        f"warning: {path} is not under a FT or WSJ folder, "
                        "not written to MongoDB",
                        file=sys.stderr,
                    )
                    failed = True

    if args.db in ("sqlite", "both"):
        with SQLiteNewsDB(args.sqlite_path) as db:
            written = db.upsert_records(records)
            total = db.count()
        print(f"SQLite: upserted {written} records into {args.sqlite_path} (table now has {total} rows)")

    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
