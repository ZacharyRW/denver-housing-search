# Denver Housing Search

Automated daily search for a rental near **Sam's Club, Lone Tree, CO** — 2bd/2ba
preferred (2bd/1ba or 1bd/1ba acceptable), dog-friendly (two dogs under 50 lbs),
townhome/duplex/house preferred, budget up to **$2,200/mo**. Results are scored by
fit, tracked over time, and published to a GitHub Pages dashboard.

**Live dashboard:** https://zacharyrw.github.io/denver-housing-search/
(after the first push + enabling Pages — see Setup).

## How it works
```
                 ┌── Craigslist ──────────────► Python scraper (reliable)
 daily 7pm run ──┤
                 └── Zillow / Apartments.com /  ► Claude-in-Chrome, using your
                     HotPads / Trulia / Rent /    real logged-in browser session,
                     Facebook Marketplace         writes data/incoming/*.json
                            │
                            ▼
              python -m scraper.run_search
              (merge · dedupe · score · rank by
               distance to work · price history)
                            │
              ┌─────────────┼───────────────┐
              ▼             ▼                ▼
        data/db.json   data/snapshots/   docs/data.json + trends.json
        (durable       YYYY-MM-DD.json   (dashboard reads these)
         history)                         │
                                          ▼
                                push to GitHub  ──►  GitHub Pages dashboard
```

## Layout
- `config.yaml` — all search criteria (budget, beds/baths, pets, area, scoring). **Edit this to tune the search.**
- `scraper/` — the pipeline (scrapers, scoring, JSON store, dashboard builder).
- `docs/` — the GitHub Pages dashboard (`index.html`) + its data (`data.json`, `trends.json`).
- `data/db.json` — durable listing history with price changes (committed).
- `data/snapshots/` — one JSON per day for long-term trends (committed).
- `SCHEDULED_TASK_PROMPT.md` — the exact prompt the daily automation runs.
- `push.sh` — one command to commit + push everything to GitHub.

## Run it manually
```bash
pip install -r requirements.txt          # first time
python3 -m scraper.run_search            # scrape + rebuild dashboard data
cd docs && python3 -m http.server 8000   # then open http://localhost:8000
                                         # (browsers block fetch() on file://, so
                                         #  use this tiny server for local preview)
```

## Setup (one time)
1. **Push to GitHub:** run `./push.sh` (uses your existing git remote + SSH key).
2. **Enable GitHub Pages:** on GitHub → repo → Settings → Pages → Source =
   "Deploy from a branch", Branch = `main`, folder = `/docs`. Save.
3. **Stay logged in** to Zillow and Facebook in Chrome so the daily task can read
   those sites through your session.
4. The daily task is scheduled for **7:00 PM**. It runs while the Claude app is
   open; if the app is closed at 7pm it runs at next launch.

## Notes on scraping reliability
Craigslist yields cleanly to Python. Every other major site (Zillow,
Apartments.com, HotPads, Trulia, Rent.com, Facebook) actively blocks bots, so
they're scraped through your real browser via Claude-in-Chrome and will
occasionally be skipped on days they show a CAPTCHA or login wall — that's
expected and logged, never fatal. The dashboard's "Source health" panel shows
which sites succeeded each day.
