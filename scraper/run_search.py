"""Main orchestrator: scrape -> normalize -> score -> store -> build dashboard.

Run daily:  python -m scraper.run_search
Options:
  --no-python   skip python scrapers (chrome-only day)
  --dry-run     don't write the database, just report
"""
from __future__ import annotations

import argparse
import json
import logging
from datetime import date
from pathlib import Path

from .common import ROOT, load_config, new_session, setup_logging
from .geo import annotate_distance, passes_filters, score_listing
from .ingest_chrome import load_incoming
from .schema import Listing
from .sites import PYTHON_SITES
from .store import Store

log = logging.getLogger("denver-housing")


def process(listings: list[Listing], cfg: dict) -> list[Listing]:
    """Annotate distance + score + deal flag, then apply hard filters."""
    work = cfg["location"]["work"]
    kept = []
    for li in listings:
        annotate_distance(li, work["lat"], work["lon"])
        li.score = score_listing(li, cfg)
        if li.price is not None and li.price <= cfg["search"]["deal_threshold"]:
            li.is_deal = True
        if passes_filters(li, cfg):
            kept.append(li)
    return kept


def run(no_python: bool = False, dry_run: bool = False) -> dict:
    cfg = load_config()
    data_dir = ROOT / cfg["output"]["data_dir"]
    snap_dir = data_dir / "snapshots"
    incoming_dir = data_dir / "incoming"
    data_dir.mkdir(parents=True, exist_ok=True)
    snap_dir.mkdir(parents=True, exist_ok=True)

    setup_logging(ROOT / "run.log")
    log.info("=== Denver housing search run %s ===", date.today().isoformat())

    store = None if dry_run else Store(data_dir / "db.json")
    session = new_session()
    seen_uids: set[str] = set()
    summary = {"date": date.today().isoformat(), "sites": {}, "kept_total": 0, "deals": 0}

    # --- python-engine sites ---
    if not no_python:
        for name, cfg_site in cfg["sites"].items():
            if cfg_site.get("engine") != "python" or not cfg_site.get("enabled"):
                continue
            mod = PYTHON_SITES.get(name)
            if not mod:
                continue
            try:
                raw = mod.scrape(cfg, session)
                kept = process(raw, cfg)
                for li in kept:
                    seen_uids.add(li.uid)
                    if store:
                        store.upsert(li)
                summary["sites"][name] = {"found": len(raw), "kept": len(kept), "ok": True}
                if store:
                    store.record_run_stat(name, len(raw), len(kept), True)
                log.info("%s: found %d, kept %d", name, len(raw), len(kept))
            except Exception as e:  # noqa: BLE001 - one site must not kill the run
                summary["sites"][name] = {"found": 0, "kept": 0, "ok": False, "note": str(e)}
                if store:
                    store.record_run_stat(name, 0, 0, False, str(e)[:200])
                log.warning("%s FAILED: %s", name, e)

    # --- chrome-ingested sites (zillow, facebook, ...) ---
    chrome_raw = load_incoming(incoming_dir)
    if chrome_raw:
        by_source: dict[str, int] = {}
        kept = process(chrome_raw, cfg)
        for li in kept:
            seen_uids.add(li.uid)
            by_source[li.source] = by_source.get(li.source, 0) + 1
            if store:
                store.upsert(li)
        for src, n in by_source.items():
            summary["sites"][src] = {"found": n, "kept": n, "ok": True, "via": "chrome"}
            if store:
                store.record_run_stat(src, n, n, True, "chrome ingest")
        log.info("chrome ingest: kept %d across %s", len(kept), list(by_source))

    # --- finalize ---
    if store:
        gone = store.mark_missing_gone(seen_uids)
        store.record_market_snapshot()
        store.commit()
        active = store.active_listings()
        summary["kept_total"] = len(active)
        summary["deals"] = sum(1 for a in active if a.get("is_deal"))
        log.info("active listings: %d (%d deals), %d marked gone",
                 len(active), summary["deals"], gone)

        # write a create-only JSON snapshot for durable trend history
        snap_path = snap_dir / f"{date.today().isoformat()}.json"
        snap_path.write_text(json.dumps(active, indent=2, default=str))

        # build the published dashboard data
        from .build_dashboard import build
        build(cfg, store)
        store.close()

    log.info("run complete: %s", json.dumps(summary))
    return summary


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-python", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    s = run(no_python=args.no_python, dry_run=args.dry_run)
    print(json.dumps(s, indent=2))


if __name__ == "__main__":
    main()
