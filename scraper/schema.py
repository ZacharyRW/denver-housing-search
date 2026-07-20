"""Common listing schema + normalization used by every site scraper."""
from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import Optional


@dataclass
class Listing:
    source: str                      # e.g. "craigslist"
    source_id: str                   # site's own id when available
    url: str
    title: str = ""
    price: Optional[int] = None      # monthly rent, USD
    beds: Optional[float] = None
    baths: Optional[float] = None
    sqft: Optional[int] = None
    property_type: str = ""          # townhome/duplex/house/condo/apartment/""
    address: str = ""
    city: str = ""
    zipcode: str = ""
    lat: Optional[float] = None
    lon: Optional[float] = None
    dogs_allowed: Optional[bool] = None
    pet_notes: str = ""
    posted_at: str = ""              # ISO date if known
    scraped_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    # Computed downstream:
    distance_mi: Optional[float] = None
    score: Optional[float] = None
    is_deal: bool = False

    @property
    def uid(self) -> str:
        """Stable dedupe key across days."""
        if self.source_id:
            return f"{self.source}:{self.source_id}"
        basis = (self.url or f"{self.title}{self.price}{self.address}").lower()
        return f"{self.source}:{hashlib.sha1(basis.encode()).hexdigest()[:16]}"

    def to_dict(self) -> dict:
        d = asdict(self)
        d["uid"] = self.uid
        return d


# ---- parsing helpers -------------------------------------------------------

_PRICE_RE = re.compile(r"\$?\s*([\d,]{3,7})")
_BED_RE = re.compile(r"(\d+(?:\.\d)?)\s*(?:bd|bed|br|bedroom)", re.I)
_BATH_RE = re.compile(r"(\d+(?:\.\d)?)\s*(?:ba|bath)", re.I)
_SQFT_RE = re.compile(r"([\d,]{3,6})\s*(?:sq\s?ft|sqft|ft2|ft²)", re.I)
_ZIP_RE = re.compile(r"\b(80\d{3})\b")

_TYPE_MAP = [
    ("townhome", ["townhome", "townhouse", "town home", " twnhm"]),
    ("duplex", ["duplex", "triplex", "half duplex"]),
    ("house", ["house", "single family", "single-family", "sfh", "detached"]),
    ("condo", ["condo", "condominium"]),
    ("apartment", ["apartment", "apt"]),
]

_NO_DOG_RE = re.compile(r"no\s+(?:pets|dogs)|pets?\s*:\s*no|cats?\s+only", re.I)
_DOG_OK_RE = re.compile(r"dogs?\s+(?:ok|okay|allowed|welcome|friendly)|pet\s+friendly|pets?\s+(?:ok|allowed|welcome)", re.I)


def parse_price(text: str) -> Optional[int]:
    if not text:
        return None
    m = _PRICE_RE.search(text.replace(",", ","))
    if not m:
        return None
    try:
        val = int(m.group(1).replace(",", ""))
        return val if 200 <= val <= 20000 else None
    except ValueError:
        return None


def parse_beds(text: str) -> Optional[float]:
    m = _BED_RE.search(text or "")
    if m:
        return float(m.group(1))
    if re.search(r"\bstudio\b", text or "", re.I):
        return 0.0
    return None


def parse_baths(text: str) -> Optional[float]:
    m = _BATH_RE.search(text or "")
    return float(m.group(1)) if m else None


def parse_sqft(text: str) -> Optional[int]:
    m = _SQFT_RE.search(text or "")
    return int(m.group(1).replace(",", "")) if m else None


def parse_zip(text: str) -> str:
    m = _ZIP_RE.search(text or "")
    return m.group(1) if m else ""


def guess_type(text: str) -> str:
    t = (text or "").lower()
    for canonical, needles in _TYPE_MAP:
        if any(n in t for n in needles):
            return canonical
    return ""


def guess_dogs(text: str) -> Optional[bool]:
    t = text or ""
    if _NO_DOG_RE.search(t):
        return False
    if _DOG_OK_RE.search(t):
        return True
    return None
