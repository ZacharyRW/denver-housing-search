"""Craigslist (denver) — most scrape-friendly source.

Craigslist splits the data we need across two places on the search page, both in
the same order:
  * JSON-LD ItemList  -> bedrooms, bathrooms, latitude, longitude, city, name
  * HTML result rows  -> price, listing URL, location label, title
We merge them by position index (verified: names line up 1:1).
"""
from __future__ import annotations

import logging

from bs4 import BeautifulSoup

from ..common import polite_get
from ..schema import Listing, guess_type, parse_price
from .base import extract_jsonld, looks_blocked

log = logging.getLogger("denver-housing")

BASE = ("https://denver.craigslist.org/search/apa"
        "?min_price=700&max_price={maxp}&min_bedrooms=1&max_bedrooms=2"
        "&pets_dog=1&availabilityMode=0&sort=date")


def scrape(cfg, session) -> list[Listing]:
    maxp = int(cfg["search"]["max_rent"] * 1.15)
    resp = polite_get(session, BASE.format(maxp=maxp))
    if resp is None:
        raise RuntimeError("craigslist: request failed / blocked")
    if looks_blocked(resp.text):
        raise RuntimeError("craigslist: page looks blocked")

    soup = BeautifulSoup(resp.text, "lxml")

    # JSON-LD items (ordered) -> geo + beds/baths
    ld_items = []
    for blob in extract_jsonld(soup):
        if isinstance(blob, dict) and blob.get("@type") == "ItemList":
            ld_items = blob.get("itemListElement", [])
            break

    # HTML rows (same order) -> price + url + location
    rows = soup.select("li.cl-static-search-result")

    listings: list[Listing] = []
    n = max(len(ld_items), len(rows))
    for i in range(n):
        item = (ld_items[i].get("item", {}) if i < len(ld_items) else {}) or {}
        row = rows[i] if i < len(rows) else None

        a = row.select_one("a") if row else None
        url = a.get("href", "") if a else item.get("url", "")
        title = ""
        price = None
        city = item.get("address", {}).get("addressLocality", "") if isinstance(item.get("address"), dict) else ""
        if row:
            t = row.select_one(".title")
            title = (t.get_text(strip=True) if t else row.get("title", "")) or ""
            p = row.select_one(".price")
            price = parse_price(p.get_text()) if p else None
            loc = row.select_one(".location")
            if loc and loc.get_text(strip=True):
                city = loc.get_text(strip=True)
        if not title:
            title = item.get("name", "")

        addr = item.get("address", {}) if isinstance(item.get("address"), dict) else {}
        beds = _num(item.get("numberOfBedrooms"))
        baths = _num(item.get("numberOfBathroomsTotal"))
        lat = _num(item.get("latitude"))
        lon = _num(item.get("longitude"))

        if not url and not title:
            continue

        listings.append(Listing(
            source="craigslist",
            source_id=_id_from_url(url),
            url=url,
            title=title,
            price=price,                       # price only from the HTML .price cell
            beds=beds,
            baths=baths,
            property_type=guess_type(title),
            address=addr.get("streetAddress", "") if addr else "",
            city=city,
            zipcode=str(addr.get("postalCode", "")) if addr else "",
            lat=lat,
            lon=lon,
            dogs_allowed=True,                 # search filtered pets_dog=1
            pet_notes="craigslist pets_dog filter",
        ))
    return listings


def _num(v):
    try:
        return float(v) if v not in (None, "", 0, "0") else (0.0 if v in (0, "0") else None)
    except (ValueError, TypeError):
        return None


def _id_from_url(url: str) -> str:
    # craigslist urls end with a base62 id like /wZUTr5LUAA6eD4Ncvszfma
    tail = (url or "").rstrip("/").split("/")[-1]
    return tail[:24] if tail else ""
