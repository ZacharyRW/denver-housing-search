"""Shared parsing helpers for site scrapers."""
from __future__ import annotations

import json
import logging

log = logging.getLogger("denver-housing")


def extract_jsonld(soup):
    """Return a list of parsed JSON-LD objects from a page."""
    out = []
    for tag in soup.find_all("script", attrs={"type": "application/ld+json"}):
        try:
            data = json.loads(tag.string or tag.get_text() or "")
        except (json.JSONDecodeError, TypeError):
            continue
        if isinstance(data, list):
            out.extend(data)
        else:
            out.append(data)
    return out


def extract_next_data(soup):
    """Return parsed __NEXT_DATA__ blob (Next.js sites like Trulia) or None."""
    tag = soup.find("script", id="__NEXT_DATA__")
    if not tag:
        return None
    try:
        return json.loads(tag.string or tag.get_text() or "")
    except (json.JSONDecodeError, TypeError):
        return None


def looks_blocked(html: str) -> bool:
    low = (html or "").lower()
    signals = ["press and hold", "captcha", "are you a human", "unusual traffic",
               "access denied", "px-captcha", "perimeterx", "verify you are"]
    return any(s in low for s in signals)
