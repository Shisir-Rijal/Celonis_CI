"""Extract structured entities from chunk text using regular expressions.

Detects three entity types:
- Emails:  user@domain.com
- URLs:    http(s)://...
- Phones:  +49 89 123456 / (089) 123-456 / 089/123456
"""

import re

_EMAIL = re.compile(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}")
_URL = re.compile(r"https?://[^\s<>\"{}|\\^\[\]]+")
_PHONE = re.compile(r"(?:\+\d{1,3}[\s.\-])?\(?\d{2,5}\)?[\s./\-]\d{3,8}(?:[\s./\-]\d{2,5})?")


def extract_entities(text: str) -> list[str]:
    """Return a deduplicated list of emails, URLs, and phone numbers found in text."""
    matches = (
        _EMAIL.findall(text)
        + _URL.findall(text)
        + _PHONE.findall(text)
    )
    seen: set[str] = set()
    result: list[str] = []
    for entity in matches:
        entity = entity.strip()
        if entity not in seen:
            seen.add(entity)
            result.append(entity)
    return result
