"""Distance + scoring. Straight-line miles as a drive-time proxy (no API key)."""
from __future__ import annotations

import math
from typing import Optional

from .schema import Listing

# Rough ZIP centroid lookup for the south Denver metro so listings without
# explicit lat/lon can still be ranked by distance.
ZIP_CENTROIDS = {
    "80124": (39.5378, -104.8769),  # Lone Tree (work)
    "80130": (39.5440, -104.9200),  # Highlands Ranch S
    "80126": (39.5470, -104.9640),  # Highlands Ranch
    "80129": (39.5390, -105.0080),  # Highlands Ranch W
    "80134": (39.5170, -104.7690),  # Parker
    "80138": (39.5180, -104.7000),  # Parker E
    "80112": (39.5760, -104.8760),  # Centennial / Greenwood Village
    "80111": (39.6120, -104.8760),  # Greenwood Village
    "80121": (39.6120, -104.9500),  # Littleton / Centennial
    "80122": (39.5800, -104.9540),  # Centennial
    "80016": (39.5850, -104.7300),  # Aurora SE
    "80015": (39.6072, -104.7828),  # Aurora (home)
    "80013": (39.6570, -104.7690),  # Aurora
    "80108": (39.4600, -104.8600),  # Castle Pines / Castle Rock N
    "80109": (39.3720, -104.8900),  # Castle Rock W
    "80104": (39.3720, -104.8300),  # Castle Rock E
    "80110": (39.6450, -105.0150),  # Englewood
    "80113": (39.6450, -104.9640),  # Englewood
    "80120": (39.6000, -105.0130),  # Littleton
    "80123": (39.6180, -105.0700),  # Littleton W
}


def haversine_mi(lat1, lon1, lat2, lon2) -> float:
    r = 3958.8  # earth radius, miles
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlmb = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlmb / 2) ** 2
    return r * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def resolve_coords(li: Listing) -> Optional[tuple]:
    if li.lat is not None and li.lon is not None:
        return (li.lat, li.lon)
    if li.zipcode and li.zipcode in ZIP_CENTROIDS:
        return ZIP_CENTROIDS[li.zipcode]
    return None


def annotate_distance(li: Listing, work_lat: float, work_lon: float) -> None:
    coords = resolve_coords(li)
    if coords:
        li.distance_mi = round(haversine_mi(coords[0], coords[1], work_lat, work_lon), 1)


def score_listing(li: Listing, cfg: dict) -> float:
    """0..100 composite. Higher = better fit."""
    s = cfg["search"]
    w = cfg["scoring"]

    # --- layout score ---
    layout_score = 0.0
    for lay in s["layouts"]:
        if li.beds is not None and li.baths is not None:
            if li.beds == lay["beds"] and li.baths >= lay["baths"]:
                layout_score = max(layout_score, lay["weight"])
    if layout_score == 0 and li.beds is not None:
        # partial credit for right bed count even if baths unknown
        for lay in s["layouts"]:
            if li.beds == lay["beds"]:
                layout_score = max(layout_score, lay["weight"] * 0.6)
    layout_score = layout_score / 100.0

    # --- price score (cheaper vs ceiling = better) ---
    price_score = 0.0
    if li.price:
        if li.price <= s["max_rent"]:
            # linear from 1.0 at $0 headroom... clamp; cheaper is better
            price_score = min(1.0, (s["max_rent"] - li.price) / s["max_rent"] + 0.4)
        else:
            over = (li.price - s["max_rent"]) / s["max_rent"]
            price_score = max(0.0, 0.3 - over)  # over budget sinks fast

    # --- distance score ---
    dist_score = 0.3
    if li.distance_mi is not None:
        soft = cfg["location"]["soft_radius_miles"]
        dist_score = max(0.0, 1.0 - (li.distance_mi / (soft * 1.5)))

    # --- property type score ---
    pref = [p.lower() for p in s["property_types_preferred"]]
    type_score = 0.4
    if li.property_type:
        type_score = 1.0 if li.property_type in pref else 0.5

    composite = (
        w["weight_layout"] * layout_score
        + w["weight_price"] * price_score
        + w["weight_distance"] * dist_score
        + w["weight_type"] * type_score
    ) * 100.0
    return round(composite, 1)


def passes_filters(li: Listing, cfg: dict) -> bool:
    """Hard filters: within radius, within bed range, not over hard budget, dog-safe."""
    s = cfg["search"]
    loc = cfg["location"]
    # bedrooms
    if li.beds is not None and not (s["min_beds"] <= li.beds <= s["max_beds"]):
        return False
    # budget (allow a little slack; scoring handles the rest)
    if li.price is not None and li.price > s["max_rent"] * 1.15:
        return False
    # dogs: drop only if explicitly no-dogs
    if s["pets"].get("require_dog_friendly") and li.dogs_allowed is False:
        return False
    # distance hard radius
    if li.distance_mi is not None and li.distance_mi > loc["hard_radius_miles"]:
        return False
    return True
