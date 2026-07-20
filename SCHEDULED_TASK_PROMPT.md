# Daily Denver Housing Search — Scheduled Task Prompt

This is the exact, self-contained prompt run automatically every evening. Each
run starts with no memory of previous runs, so everything needed is written
here. It is committed to the repo on purpose so the automation can be rebuilt if
the computer is lost.

---

You are running the daily Denver rental housing search. Work through the steps in
order. **One failing site must never stop the whole run** — log it and continue.

## Search criteria (from config.yaml — do not hardcode, but this is the intent)
- Budget: monthly rent up to **$2,200** (flag anything <= $1,950 as a deal).
- Layout, best first: **2 bed / 2 bath**, then 2 bed / 1 bath, then 1 bed / 1 bath.
- Property type, best first: **townhome, duplex, house**; condo/apartment allowed.
- Pets: **two dogs, both under 50 lbs — must allow dogs.**
- Location: south Denver metro, ranked by closeness to **Sam's Club, Lone Tree**
  (9101 Westview Rd, Lone Tree, CO 80124). Nearer scores higher. "Anywhere
  reasonable" — keep a wide net across Lone Tree, Highlands Ranch, Parker,
  Centennial, Castle Pines, Castle Rock, Aurora, Englewood, Littleton.

## Step 0 — Locate the project
```bash
REPO=$(find /sessions -maxdepth 4 -type d -name denver-housing-search 2>/dev/null | head -1)
echo "repo: $REPO"; cd "$REPO"
mkdir -p data/incoming
```
If `$REPO` is empty, the connected folder isn't mounted — stop and report that.

## Step 1 — Scrape the browser-only sites with Claude-in-Chrome
These sites block plain scraping, so use the Claude-in-Chrome tools with the
user's real, logged-in browser session. **If Chrome isn't connected, or a site
shows a login wall / CAPTCHA / "press and hold", skip that site**: write an empty
list to its incoming file with a note, and move on. Do not spend more than a few
minutes per site.

For each site below: open the URL, let results load, read the listing cards, and
extract up to ~40 listings. Write them to `data/incoming/<site>.json` as a JSON
list of objects with these keys (all optional except url or title):
```json
[{"title":"", "price":1650, "beds":2, "baths":2, "sqft":950,
  "property_type":"townhome", "address":"", "city":"", "zipcode":"",
  "lat":null, "lon":null, "url":"", "dogs_allowed":true, "posted_at":""}]
```
Rules: price is monthly rent as a number; beds/baths as numbers; property_type is
one of townhome/duplex/house/condo/apartment or ""; set dogs_allowed=true only if
the listing says dogs/pets are welcome. Skip listings clearly over ~$2,530.

Sites (write to the filename in parentheses):
1. **Zillow** (`data/incoming/zillow.json`)
   https://www.zillow.com/lone-tree-co/rentals/
   Apply filters: For Rent, Beds 1–2, Price max $2,530, Pets: allowed, Home type:
   Townhomes + Houses + Condos + Apartments. Also check Highlands Ranch, Parker,
   Aurora if time allows.
2. **Apartments.com** (`data/incoming/apartments.json`)
   https://www.apartments.com/lone-tree-co-highlands-ranch-co-parker-co/1-to-2-bedrooms-under-2600-pet-friendly-dog/
3. **HotPads** (`data/incoming/hotpads.json`)
   https://hotpads.com/lone-tree-co/apartments-for-rent?beds=1-2&price=700-2530&pets=dogs
4. **Trulia** (`data/incoming/trulia.json`)
   https://www.trulia.com/for_rent/Lone_Tree,CO/1-2p_beds/0-2530_price/DOGS_pet/
5. **Rent.com** (`data/incoming/rentdotcom.json`)
   https://www.rent.com/colorado/lone-tree — filter 1–2 beds, dog-friendly, under $2,530.
6. **Facebook Marketplace** (`data/incoming/facebook.json`)
   https://www.facebook.com/marketplace/denver/propertyrentals?minPrice=700&maxPrice=2530
   Search: "2 bedroom dog friendly". Use the logged-in session. Private-landlord
   posts here are valuable. If logged out, skip and note it.

Write each file as you finish that site so a later failure never loses earlier work.

## Step 2 — Run the pipeline (Craigslist + merge + score + dashboard)
```bash
cd "$REPO" && python3 -m scraper.run_search
```
This scrapes Craigslist (reliable via Python), ingests every
`data/incoming/*.json` you just wrote, dedupes, scores, ranks by fit, updates
`data/db.json` (the durable history), writes a dated snapshot to
`data/snapshots/`, and regenerates `docs/data.json` + `docs/trends.json` for the
dashboard. It prints a JSON summary — capture it.

## Step 3 — Publish to GitHub (so the dashboard updates and data is backed up)
Repo: **https://github.com/ZacharyRW/denver-housing-search** (GitHub Pages serves
the dashboard from `/docs`). The sandbox cannot use git directly (the mounted
folder blocks file deletion, which git needs). Push using the first method that
works:

**A. GitHub connector (preferred, if authorized).** If GitHub MCP tools are
available, commit these changed files via the "create or update file contents"
API (read each file, push its contents to branch `main`):
`docs/data.json`, `docs/trends.json`, `data/db.json`,
`data/snapshots/<today>.json`. Commit message: `daily search <today>`.

**B. Claude-in-Chrome fallback.** If no GitHub connector, use the logged-in
browser: go to the repo, and for each changed file use GitHub's web UI
(Add file → Upload files, or edit the file) to commit the new contents to `main`.
Prioritize `docs/data.json` and `docs/trends.json` (these drive the dashboard),
then `data/db.json` and today's snapshot.

**C. If neither works**, leave the files updated locally and note in the summary
that a manual `git push` is needed. The local `data/db.json` still preserves the
day's history.

## Step 4 — Report
Summarize: how many active listings, how many deals (<= $1,950), how many within
10 miles of work, the best 5 by fit (rent, beds/baths, type, distance, link),
which sites succeeded vs. were blocked, and whether the GitHub publish succeeded.
