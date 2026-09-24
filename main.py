"""Parse ProQuest news export .txt files and load them into SQLite (and
optionally MongoDB).

Each input may be a single .txt file or a directory, in which case every
*.txt file under it is parsed. Records are upserted keyed by their
ProQuest document id (proquest_id), so re-running on overlapping files
(e.g. new exports whose date range overlaps an older file) is safe and
de-duplicates automatically.

Usage:
    python main.py                          # scans data/FT and data/WSJ
    python main.py data/FT data/WSJ
    python main.py "data/FT/ProQuestDocuments-1996-*.txt"   # one year
    python main.py data/FT/ProQuestDocuments-1996-05-31-第一頁.txt
    python main.py data/FT data/WSJ --with-mongo
"""
from __future__ import annotations

import argparse
import glob
import sys
from pathlib import Path

from newsdb.db.sqlite_db import SQLiteNewsDB
from newsdb.parser import parse_file

DEFAULT_INPUTS = ["data/FT", "data/WSJ"]


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
        "--sqlite-path", default="data/sqlite/news.db", help="Output SQLite database path"
    )
    parser.add_argument(
        "--with-mongo", action="store_true", help="Also upsert records into MongoDB"
    )
    parser.add_argument(
        "--mongo-uri", default=None, help="MongoDB URI (defaults to $MONGODB_URI or localhost)"
    )
    args = parser.parse_args()

    txt_files = collect_txt_files(args.inputs)
    if not txt_files:
        print("No .txt files found to parse.", file=sys.stderr)
        return 1
    print(f"Found {len(txt_files)} .txt file(s)")

    records: list[dict] = []
    for path in txt_files:
        try:
            file_records = parse_file(path)
        except Exception as exc:  # noqa: BLE001 - keep ingesting the rest of the files
            print(f"warning: failed to parse {path}: {exc}", file=sys.stderr)
            continue
        print(f"  {path}: {len(file_records)} records")
        records.extend(file_records)

    unique_ids = {r["proquest_id"] for r in records if r.get("proquest_id")}
    print(
        f"Parsed {len(records)} records total, "
        f"{len(unique_ids)} unique by proquest_id "
        f"({len(records) - len(unique_ids)} duplicate)"
    )

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
