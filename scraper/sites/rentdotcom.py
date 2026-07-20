"""Rent.com — JSON-LD based; fails gracefully when blocked."""
from __future__ import annotations

import logging

from bs4 import BeautifulSoup

from ..common import polite_get
from ..schema import Listing, guess_type, parse_zip
from .base import extract_jsonld, looks_blocked

log = logging.getLogger("denver-housing")

AREA_SLUGS = {
    "Lone Tree, CO": "lone-tree-co",
    "Highlands Ranch, CO": "highlands-ranch-co",
    "Parker, CO": "parker-co",
    "Centennial, CO": "centennial-co",
    "Littleton, CO": "littleton-co",
    "Aurora, CO": "aurora-co",
}


def scrape(cfg, session) -> list[Listing]:
    listings: list[Listing] = []
    blocked_any = False
    for area in cfg["location"]["areas"]:
        slug = AREA_SLUGS.get(area)
        if not slug:
            continue
        url = f"https://www.rent.com/colorado/{slug}/pet-friendly-apartments"
        resp = polite_get(session, url)
        if resp is None or looks_blocked(resp.text):
            blocked_any = True
            continue
        soup = BeautifulSoup(resp.text, "lxml")
        for blob in extract_jsonld(soup):
            items = blob.get("itemListElement", []) if isinstance(blob, dict) else []
            for it in items:
                node = it.get("item", it) if isinstance(it, dict) else {}
                urlx = node.get("url", "")
                name = node.get("name", "")
                if not urlx:
                    continue
                listings.append(Listing(
                    source="rentdotcom", source_id=urlx.rstrip("/").split("/")[-1],
                    url=urlx, title=name, property_type=guess_type(name),
                    zipcode=parse_zip(name), dogs_allowed=True,
                    pet_notes="rent.com pet-friendly filter",
                ))
    if not listings and blocked_any:
        raise RuntimeError("rent.com: blocked on all areas (use chrome engine)")
    return listings
