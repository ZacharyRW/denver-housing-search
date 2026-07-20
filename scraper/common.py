"""Shared helpers: config loading, HTTP session, logging."""
from __future__ import annotations

import logging
import os
import random
import time
from pathlib import Path

import requests
import yaml

ROOT = Path(__file__).resolve().parent.parent
CONFIG_PATH = ROOT / "config.yaml"

log = logging.getLogger("denver-housing")

# Rotate a few realistic desktop user agents to reduce trivial blocking.
_USER_AGENTS = [
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 "
    "(KHTML, like Gecko) Version/17.4 Safari/605.1.15",
]


def load_config() -> dict:
    with open(CONFIG_PATH, "r") as f:
        return yaml.safe_load(f)


def new_session() -> requests.Session:
    s = requests.Session()
    s.headers.update({
        "User-Agent": random.choice(_USER_AGENTS),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
        "Cache-Control": "no-cache",
    })
    return s


def polite_get(session: requests.Session, url: str, timeout: int = 15, **kw):
    """GET with a short jittered delay + limited retry. Returns Response or None.

    Bails immediately on 403/429: those mean the site's anti-bot blocked us and
    retrying from plain Python won't help — the Claude-in-Chrome engine covers
    those sites instead. Keeping this fast matters because the daily task walks
    many sites/areas.
    """
    for attempt in range(2):
        try:
            time.sleep(random.uniform(0.8, 2.0))  # be polite / avoid rate limits
            resp = session.get(url, timeout=timeout, **kw)
            if resp.status_code == 200:
                return resp
            if resp.status_code in (403, 429, 401):
                log.info("GET %s -> HTTP %s (blocked; chrome engine will cover)", url, resp.status_code)
                return None  # don't waste time retrying anti-bot walls
            log.warning("GET %s -> HTTP %s (attempt %d)", url, resp.status_code, attempt + 1)
        except requests.RequestException as e:
            log.warning("GET %s failed: %s (attempt %d)", url, e, attempt + 1)
    return None


def setup_logging(logfile: Path | None = None):
    handlers = [logging.StreamHandler()]
    if logfile:
        handlers.append(logging.FileHandler(logfile))
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
        handlers=handlers,
    )
