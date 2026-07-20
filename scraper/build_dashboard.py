"""Emit the JSON files the GitHub Pages dashboard reads (docs/data.json, trends.json)."""
from __future__ import annotations

import json
from datetime import datetime, timezone

from .common import ROOT
from .store import Store


def build(cfg: dict, store: Store) -> None:
    docs = ROOT / cfg["output"]["docs_dir"]
    docs.mkdir(parents=True, exist_ok=True)

    listings = store.active_listings()
    # attach per-listing price history (for sparkline / change detection)
    for li in listings:
        hist = store.price_history_for(li["uid"])
        li["price_history"] = hist
        li["price_changed"] = len({h["price"] for h in hist}) > 1
        li["days_on_market"] = _days_between(li.get("first_seen"), li.get("last_seen"))

    data = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "criteria": {
            "max_rent": cfg["search"]["max_rent"],
            "deal_threshold": cfg["search"]["deal_threshold"],
            "work": cfg["location"]["work"]["label"],
        },
        "count": len(listings),
        "deals": sum(1 for x in listings if x.get("is_deal")),
        "listings": listings,
    }
    (docs / "data.json").write_text(json.dumps(data, indent=2, default=str))

    trends = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "market": store.market_trend(),
        "run_stats": store.run_stats_recent(),
    }
    (docs / "trends.json").write_text(json.dumps(trends, indent=2, default=str))


def _days_between(a: str | None, b: str | None):
    try:
        da = datetime.fromisoformat(a)
        db = datetime.fromisoformat(b)
        return max(0, (db - da).days)
    except (TypeError, ValueError):
        return 0
