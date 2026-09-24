"""Parse ProQuest publication dates such as "Aug 11, 2026"."""
from __future__ import annotations

import re
from datetime import date

# Month names are matched by hand: strptime("%b") depends on the OS locale.
_MONTHS = {
    "jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6,
    "jul": 7, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12,
}
_TEXT_DATE_RE = re.compile(r"^([A-Za-z]{3,9})\.?(\d{1,2}),?(\d{4})$")
_ISO_DATE_RE = re.compile(r"^(\d{4})-(\d{2})-(\d{2})$")


def parse_publication_date(raw: str | None) -> date | None:
    """Return the date, or None if `raw` is missing or not a full date.

    The export sometimes inserts spaces inside the text ("Aug 11 , 2026",
    "Au g 1, 1996", "Aug 10, 19 96"), so all whitespace is dropped before
    matching. Also accepts "Sept". Partial dates such as "May 1996" return
    None; callers keep the raw string.
    """
    if not raw:
        return None
    text = re.sub(r"\s+", "", raw)
    try:
        match = _TEXT_DATE_RE.match(text)
        if match:
            month = _MONTHS.get(match.group(1)[:3].lower())
            if month:
                return date(int(match.group(3)), month, int(match.group(2)))
            return None
        match = _ISO_DATE_RE.match(text)
        if match:
            return date(int(match.group(1)), int(match.group(2)), int(match.group(3)))
    except ValueError:  # e.g. Feb 30
        return None
    return None
