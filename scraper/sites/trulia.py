"""Trulia (Zillow-owned). Uses __NEXT_DATA__; strong anti-bot -> graceful fail."""
from __future__ import annotations

import logging

from bs4 import BeautifulSoup

from ..common import polite_get
from ..schema import Listing, guess_type
from .base import extract_next_data, looks_blocked

log = logging.getLogger("denver-housing")


def scrape(cfg, session) -> list[Listing]:
    maxp = int(cfg["search"]["max_rent"] * 1.15)
    url = (f"https://www.trulia.com/for_rent/Lone_Tree,CO/1p_beds/0-{maxp}_price/"
           f"DOGS_pet/")
    resp = polite_get(session, url)
    if resp is None or looks_blocked(resp.text):
        raise RuntimeError("trulia: blocked (use chrome engine)")
    soup = BeautifulSoup(resp.text, "lxml")
    data = extract_next_data(soup)
    if not data:
        raise RuntimeError("trulia: no __NEXT_DATA__ (page changed or blocked)")

    listings: list[Listing] = []
    homes = _find_homes(data)
    for h in homes:
        try:
            price = h.get("price", {}).get("price") if isinstance(h.get("price"), dict) else None
            loc = h.get("location", {}) or {}
            beds = (h.get("bedrooms", {}) or {}).get("formattedValue")
            listings.append(Listing(
                source="trulia",
                source_id=str(h.get("url", "")).rstrip("/").split("/")[-1],
                url="https://www.trulia.com" + h.get("url", "") if h.get("url", "").startswith("/") else h.get("url", ""),
                title=loc.get("formattedLocation", ""),
                price=int(price) if isinstance(price, (int, float)) else None,
                property_type=guess_type(str(h.get("propertyType", ""))),
                address=loc.get("formattedLocation", ""),
                zipcode=str(loc.get("zipCode", "")),
                lat=(loc.get("coordinates", {}) or {}).get("latitude"),
                lon=(loc.get("coordinates", {}) or {}).get("longitude"),
                dogs_allowed=True,
                pet_notes="trulia dogs filter",
            ))
        except Exception as e:  # noqa: BLE001 - defensive on unknown shapes
            log.debug("trulia parse skip: %s", e)
    if not listings:
        raise RuntimeError("trulia: parsed 0 homes (shape changed)")
    return listings


def _find_homes(obj, _depth=0):
    """Walk the NEXT_DATA tree looking for a list of home-like dicts."""
    if _depth > 8:
        return []
    if isinstance(obj, list):
        if obj and isinstance(obj[0], dict) and "url" in obj[0] and (
            "price" in obj[0] or "bedrooms" in obj[0]
        ):
            return obj
        for x in obj:
            found = _find_homes(x, _depth + 1)
            if found:
                return found
    elif isinstance(obj, dict):
        for v in obj.values():
            found = _find_homes(v, _depth + 1)
            if found:
                return found
    return []
