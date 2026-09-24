"""Parser for ProQuest newspaper export .txt files.

File layout (observed from news/ProQuestDocuments-*.txt):
  - Records are separated by a line of 60 underscores.
  - Within a record, fields are separated by a blank line. Each field block's
    first line is either a bare title, a bare URL, or "<中文欄位名>: <內容>".
    A field's content may itself span multiple lines (e.g. 全文/full_text)
    without a blank line between them.
  - The file has a leading empty chunk before the first separator and a
    trailing footer chunk (聯絡我們 / 條款和條件) after the last separator,
    both of which are not records and are discarded.
"""
from __future__ import annotations

import re

from newsdb.dates import parse_publication_date

SEPARATOR_RE = re.compile(r"^_{10,}$", re.MULTILINE)
BLOCK_SPLIT_RE = re.compile(r"\n\s*\n")

# Chinese field label -> canonical English key
LABEL_MAP = {
    "出版物資訊": "byline",
    "摘要": "abstract",
    "連結": "link",
    "全文": "full_text",
    "主題": "subjects",
    "商業索引術語": "business_indexing_terms",
    "地點": "locations",
    "標題": "title",
    "作者": "author",
    "出版物名稱": "publication_title",
    "第一頁": "first_page",
    "出版年份": "publication_year",
    "出版日期": "publication_date",
    "區段": "section",
    "出版者": "publisher",
    "出版地": "place_of_publication",
    "出版國家/地區": "country",
    "出版物主题": "publication_subject",
    "ISSN": "issn",
    "來源類型": "source_type",
    "出版物語言": "publication_language",
    "文件類型": "document_type",
    "ProQuest 文件識別碼": "proquest_id",
    "文件 URL": "document_url",
    "文件URL": "document_url",
    "著作權": "copyright",
    "可用全文": "full_text_availability",
    "最後更新": "last_updated",
    "資料庫": "database",
    "分類": "classification",
    "公司/組織": "company_organization",
    "人員": "people",
}

# Fields whose raw value is a "; "-separated list -> stored as a list of strings
MULTI_VALUE_KEYS = {
    "subjects",
    "locations",
    "database",
    "classification",
    "company_organization",
    "people",
}

_LABEL_RE = re.compile(
    "^(" + "|".join(re.escape(k) for k in LABEL_MAP) + r"): ?(.*)$", re.DOTALL
)


def _split_records(content: str) -> list[str]:
    parts = SEPARATOR_RE.split(content)
    # Drop the empty leading chunk and the trailing footer chunk.
    return [p.strip("\n") for p in parts[1:-1] if p.strip()]


def parse_record(record_text: str) -> dict:
    """Parse a single record's raw text into a field dict."""
    blocks = [b.strip("\n") for b in BLOCK_SPLIT_RE.split(record_text.strip("\n")) if b.strip()]

    result: dict = {}
    for i, block in enumerate(blocks):
        match = _LABEL_RE.match(block)
        if match:
            key = LABEL_MAP[match.group(1)]
            value = match.group(2).strip()
            if key in MULTI_VALUE_KEYS:
                result[key] = [v.strip() for v in value.split(";") if v.strip()]
            else:
                result[key] = value
            continue

        if block.startswith("http"):
            result.setdefault("docview_url", block.strip())
        elif i == 0:
            result.setdefault("title", block.strip())
        # Anything else unrecognized is ignored (none observed in practice).

    # Normalize a few scalar types.
    if "publication_year" in result:
        try:
            result["publication_year"] = int(result["publication_year"])
        except ValueError:
            pass

    # Keep the original text; publication_date becomes a date (None if unparseable).
    raw_date = result.get("publication_date")
    if raw_date is not None:
        result["publication_date_raw"] = raw_date
        result["publication_date"] = parse_publication_date(raw_date)

    return result


def parse_file(path: str) -> list[dict]:
    """Parse a ProQuest export .txt file into a list of record dicts."""
    with open(path, encoding="utf-8") as f:
        content = f.read()
    return [parse_record(r) for r in _split_records(content)]


def parse_text(content: str) -> list[dict]:
    """Parse ProQuest export content (already read into memory) into records."""
    return [parse_record(r) for r in _split_records(content)]
