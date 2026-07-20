"""Apartments.com — JSON-LD based. Strong anti-bot; fails gracefully when blocked."""
from __future__ import annotations

import logging

from bs4 import BeautifulSoup

from ..common import polite_get
from ..schema import (Listing, guess_type, parse_baths, parse_beds, parse_price,
                      parse_zip)
from .base import extract_jsonld, looks_blocked

log = logging.getLogger("denver-housing")

# Apartments.com slug search: 2-beds, pet-friendly, under budget, south metro.
AREA_SLUGS = {
    "Lone Tree, CO": "lone-tree-co",
    "Highlands Ranch, CO": "highlands-ranch-co",
    "Parker, CO": "parker-co",
    "Centennial, CO": "centennial-co",
    "Littleton, CO": "littleton-co",
    "Aurora, CO": "aurora-co",
}


def scrape(cfg, session) -> list[Listing]:
    maxp = int(cfg["search"]["max_rent"] * 1.15)
    listings: list[Listing] = []
    blocked_any = False
    for area in cfg["location"]["areas"]:
        slug = AREA_SLUGS.get(area)
        if not slug:
            continue
        url = f"https://www.apartments.com/{slug}/min-1-bedrooms-max-{maxp}-pet-friendly-dog/"
        resp = polite_get(session, url)
        if resp is None or looks_blocked(resp.text):
            blocked_any = True
            continue
        soup = BeautifulSoup(resp.text, "lxml")
        for blob in extract_jsonld(soup):
            about = blob.get("about", []) if isinstance(blob, dict) else []
            if isinstance(about, dict):
                about = [about]
            for node in about or []:
                if not isinstance(node, dict):
                    continue
                name = node.get("name", "")
                urlx = node.get("url", "")
                if not urlx:
                    continue
                listings.append(Listing(
                    source="apartments",
                    source_id=urlx.rstrip("/").split("/")[-1],
                    url=urlx,
                    title=name,
                    property_type=guess_type(name) or "apartment",
                    address=_addr(node),
                    zipcode=parse_zip(_addr(node)),
                    dogs_allowed=True,
                    pet_notes="apartments.com pet-friendly-dog filter",
                ))
    if not listings and blocked_any:
        raise RuntimeError("apartments.com: blocked on all areas (use chrome engine)")
    return listings


def _addr(node) -> str:
    a = node.get("address", {}) if isinstance(node, dict) else {}
    if isinstance(a, dict):
        return " ".join(str(a.get(k, "")) for k in
                        ("streetAddress", "addressLocality", "addressRegion", "postalCode")).strip()
    return str(a)
