"""JSON-backed persistence with price history + daily snapshots.

Why JSON and not SQLite? The synced project folder allows creating and
overwriting files but blocks *deleting* them. SQLite needs to delete/replace
journal and lock files, so it corrupts easily here and can't be reset. A single
JSON document that we load into memory and overwrite in place is fully reliable
on this filesystem, human-readable, and diffs cleanly in git — which also makes
the trend history easy to inspect and safe against losing the computer.

Layout of data/db.json:
{
  "listings": { uid: { ...fields, first_seen, last_seen, status,
                       price_history: [ {observed_on, price}, ... ] } },
  "run_stats": { "YYYY-MM-DD": { source: {found, kept, ok, note} } },
  "market":    { "YYYY-MM-DD": { active_count, ... } }
}
"""
from __future__ import annotations

import json
import os
from datetime import date, datetime, timezone
from pathlib import Path

from .schema import Listing


class Store:
    def __init__(self, db_path: Path):
        self.path = db_path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.data = {"listings": {}, "run_stats": {}, "market": {}}
        if self.path.exists() and self.path.stat().st_size > 0:
            try:
                self.data = json.loads(self.path.read_text())
                for k in ("listings", "run_stats", "market"):
                    self.data.setdefault(k, {})
            except (json.JSONDecodeError, OSError):
                # corrupt/partial write -> start clean (we can always overwrite)
                self.data = {"listings": {}, "run_stats": {}, "market": {}}

    # --- lifecycle ----------------------------------------------------------
    def commit(self):
        """Overwrite the JSON doc in place (no delete/rename needed)."""
        text = json.dumps(self.data, indent=1, default=str)
        with open(self.path, "w") as f:
            f.write(text)
            f.flush()
            os.fsync(f.fileno())

    def close(self):
        self.commit()

    # --- upsert -------------------------------------------------------------
    def upsert(self, li: Listing) -> None:
        today = date.today().isoformat()
        now = datetime.now(timezone.utc).isoformat()
        rec = self.data["listings"].get(li.uid)
        fields = li.to_dict()
        if rec is None:
            fields["first_seen"] = now
            fields["last_seen"] = now
            fields["status"] = "active"
            fields["price_history"] = []
            self.data["listings"][li.uid] = rec = fields
        else:
            rec.update({k: fields[k] for k in fields if k not in
                        ("first_seen", "price_history")})
            rec["last_seen"] = now
            rec["status"] = "active"
        # record price history point (one per day)
        if li.price is not None:
            hist = rec.setdefault("price_history", [])
            if not any(h["observed_on"] == today for h in hist):
                hist.append({"observed_on": today, "price": li.price})
            else:
                for h in hist:
                    if h["observed_on"] == today:
                        h["price"] = li.price

    def mark_missing_gone(self, seen_uids: set[str]) -> int:
        gone = 0
        for uid, rec in self.data["listings"].items():
            if rec.get("status") == "active" and uid not in seen_uids:
                rec["status"] = "gone"
                gone += 1
        return gone

    # --- stats --------------------------------------------------------------
    def record_run_stat(self, source: str, found: int, kept: int, ok: bool, note: str = ""):
        day = self.data["run_stats"].setdefault(date.today().isoformat(), {})
        day[source] = {"found": found, "kept": kept, "ok": bool(ok), "note": note}

    def record_market_snapshot(self):
        today = date.today().isoformat()
        active = [r for r in self.data["listings"].values() if r.get("status") == "active"]
        priced = sorted(r["price"] for r in active if r.get("price") is not None)
        p2 = sorted(r["price"] for r in active if r.get("beds") == 2 and r.get("price"))
        p1 = sorted(r["price"] for r in active if r.get("beds") == 1 and r.get("price"))
        deals = sum(1 for r in active if r.get("is_deal"))

        def med(xs):
            if not xs:
                return None
            n = len(xs)
            return xs[n // 2] if n % 2 else (xs[n // 2 - 1] + xs[n // 2]) / 2

        self.data["market"][today] = {
            "run_date": today,
            "active_count": len(active),
            "eligible_count": len(priced),
            "deal_count": deals,
            "median_price": med(priced),
            "min_price": (priced[0] if priced else None),
            "avg_price": (round(sum(priced) / len(priced)) if priced else None),
            "median_2bed": med(p2),
            "median_1bed": med(p1),
        }

    # --- exports for dashboard ----------------------------------------------
    def active_listings(self) -> list[dict]:
        out = [dict(r) for r in self.data["listings"].values() if r.get("status") == "active"]
        out.sort(key=lambda r: (r.get("score") if r.get("score") is not None else -1), reverse=True)
        return out

    def price_history_for(self, uid: str) -> list[dict]:
        rec = self.data["listings"].get(uid, {})
        return sorted(rec.get("price_history", []), key=lambda h: h["observed_on"])

    def market_trend(self) -> list[dict]:
        return [self.data["market"][d] for d in sorted(self.data["market"])]

    def run_stats_recent(self, days: int = 14) -> list[dict]:
        out = []
        for day in sorted(self.data["run_stats"], reverse=True)[:days]:
            for source, s in self.data["run_stats"][day].items():
                out.append({"run_date": day, "source": source, **s})
        return out
