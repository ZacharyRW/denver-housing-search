"""Site scraper registry. Each module exposes scrape(cfg, session) -> list[Listing]."""
from . import craigslist, apartments, hotpads, rentdotcom, trulia

# name -> module. Only python-engine sites live here; zillow/facebook are
# handled by the Claude-in-Chrome path and ingested via ingest_chrome.py.
PYTHON_SITES = {
    "craigslist": craigslist,
    "apartments": apartments,
    "hotpads": hotpads,
    "rentdotcom": rentdotcom,
    "trulia": trulia,
}
