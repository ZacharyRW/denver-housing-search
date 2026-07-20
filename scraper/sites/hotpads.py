"""HotPads (Zillow-owned). Strong anti-bot -> often blocked; fails gracefully.
Kept as a python stub so the Chrome path can cover it if needed."""
from __future__ import annotations

import logging

from bs4 import BeautifulSoup

from ..common import polite_get
from ..schema import Listing, guess_type, parse_zip
from .base import extract_jsonld, looks_blocked

log = logging.getLogger("denver-housing")


def scrape(cfg, session) -> list[Listing]:
    maxp = int(cfg["search"]["max_rent"] * 1.15)
    url = (f"https://hotpads.com/lone-tree-co/apartments-for-rent"
           f"?price=800-{maxp}&beds=1-2&propertyTypes=townhouse,house,condo,apartment"
           f"&pets=dogs")
    resp = polite_get(session, url)
    if resp is None or looks_blocked(resp.text):
        raise RuntimeError("hotpads: blocked (use chrome engine)")
    soup = BeautifulSoup(resp.text, "lxml")
    listings: list[Listing] = []
    for blob in extract_jsonld(soup):
        if isinstance(blob, dict) and blob.get("@type") in ("Apartment", "SingleFamilyResidence", "Residence"):
            name = blob.get("name", "")
            urlx = blob.get("url", "")
            listings.append(Listing(
                source="hotpads", source_id=urlx.rstrip("/").split("/")[-1],
                url=urlx, title=name, property_type=guess_type(name),
                zipcode=parse_zip(name), dogs_allowed=True,
                pet_notes="hotpads dogs filter",
            ))
    if not listings:
        raise RuntimeError("hotpads: no structured listings (likely JS-rendered)")
    return listings
