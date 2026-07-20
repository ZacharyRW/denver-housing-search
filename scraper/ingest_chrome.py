"""Ingest listings scraped by Claude-in-Chrome (Zillow, Facebook, etc.).

The Chrome step writes one JSON file per site into data/incoming/<site>.json, a
list of raw listing dicts. This module normalizes them into Listing objects.
Any field is optional; missing ones are parsed from the title/text.
"""
from __future__ import annotations

import json
import logging
from pathlib import Path

from .schema import (Listing, guess_dogs, guess_type, parse_baths, parse_beds,
                     parse_price, parse_sqft, parse_zip)

log = logging.getLogger("denver-housing")


def load_incoming(incoming_dir: Path) -> list[Listing]:
    listings: list[Listing] = []
    if not incoming_dir.exists():
        return listings
    for path in sorted(incoming_dir.glob("*.json")):
        source = path.stem  # e.g. "zillow", "facebook"
        try:
            raw = json.loads(path.read_text())
        except (json.JSONDecodeError, OSError) as e:
            log.warning("ingest_chrome: could not read %s: %s", path, e)
            continue
        if isinstance(raw, dict):
            raw = raw.get("listings", raw.get("results", []))
        for item in raw or []:
            listings.append(_normalize(source, item))
        log.info("ingest_chrome: %s -> %d listings", source, len(raw or []))
    return listings


def _normalize(source: str, d: dict) -> Listing:
    text = " ".join(str(d.get(k, "")) for k in ("title", "name", "description", "text"))
    return Listing(
        source=source,
        source_id=str(d.get("id") or d.get("source_id") or ""),
        url=d.get("url", d.get("link", "")),
        title=d.get("title", d.get("name", ""))[:300],
        price=_int(d.get("price")) or parse_price(text),
        beds=_float(d.get("beds")) if d.get("beds") is not None else parse_beds(text),
        baths=_float(d.get("baths")) if d.get("baths") is not None else parse_baths(text),
        sqft=_int(d.get("sqft")) or parse_sqft(text),
        property_type=(d.get("property_type") or guess_type(text) or ""),
        address=d.get("address", ""),
        city=d.get("city", ""),
        zipcode=str(d.get("zipcode") or parse_zip(d.get("address", "") + " " + text)),
        lat=_float(d.get("lat")),
        lon=_float(d.get("lon")),
        dogs_allowed=d.get("dogs_allowed") if isinstance(d.get("dogs_allowed"), bool)
        else guess_dogs(text),
        pet_notes=d.get("pet_notes", ""),
        posted_at=d.get("posted_at", ""),
    )


def _int(v):
    try:
        return int(float(str(v).replace(",", "").replace("$", ""))) if v not in (None, "") else None
    except (ValueError, TypeError):
        return None


def _float(v):
    try:
        return float(v) if v not in (None, "") else None
    except (ValueError, TypeError):
        return None
