# Trade Calculator

A small web app for negotiating a miniatures trade live with someone else: each side adds
items (priced from a WarhammerScraper catalog import where possible, manual entry otherwise),
and the app shows running totals, the value difference, and a suggested cash top-up to balance
the trade — over a shared link, updating in real time via WebSocket.

## Local development

```bash
python -m venv .venv
.venv/Scripts/python -m pip install -r requirements.txt
.venv/Scripts/python -m uvicorn app.main:app --reload --port 8123
```

Open http://127.0.0.1:8123/

## Refreshing the catalog

The app ships with a committed `data/catalog_seed.json` snapshot so it can deploy standalone
without WarhammerScraper present. It covers every IP the scraper has data for (Warhammer 40,000,
Age of Sigmar, Horus Heresy) — faction titles and IP grouping come from WarhammerScraper's own
`factions/*.py` registry, not folder names on disk. To refresh it after WarhammerScraper
re-scrapes:

```bash
python scripts/import_catalog.py --scraper-root "C:\path\to\WarhammerScraper" --seed-out data/catalog_seed.json
```

Commit the updated `data/catalog_seed.json`.

## Tests

```bash
.venv/Scripts/python -m pytest tests/
```

## Deploying to Fly.io

```bash
fly launch --no-deploy   # first time only, confirm it picks up fly.toml as-is
fly volumes create trade_data --size 1 --region iad
fly deploy
```

The SQLite database lives on the `trade_data` volume at `/data/trade.db` — without that volume
mounted, data is lost on every redeploy. Confirm the volume exists (`fly volumes list`) before
trusting a deployed room to persist.

## Coverage gaps

Items added with a manually-entered price and no catalog match are logged to the `coverage_gaps`
table, visible at `/gaps`. This is a queue for extending the WarhammerScraper catalog (e.g.
Genestealer Cults, Death Korps of Krieg aren't covered yet) — a separate local script (not part of
this repo) is expected to poll `/gaps` and file the gaps as follow-up scraping work.

## Kit-size (models-per-box) gaps

warhammer.com's bot detection blocks server-side scraping of individual product pages (the same
wall that blocks the core catalog scrape — see WarhammerScraper's README), so a kit size can't be
fetched live when someone picks a unit in the trade UI. Instead: whenever someone adds a catalog
item with no known `models_per_box`, it's queued in the `kit_size_gaps` table (ranked by how many
times people have actually tried to trade it) rather than just prompting for manual entry.

To process the queue in a browser-assisted scrape session:

```bash
python scripts/export_kit_size_gap_urls.py > gaps.json
# ...run the browser-assisted workflow from WarhammerScraper/scripts/scrape_kit_sizes.py
# against gaps.json's URLs, collect the first-bullet text per item...
python /path/to/WarhammerScraper/scripts/scrape_kit_sizes.py --merge collected.json
# rebuild the affected faction xlsx(s), then re-run this repo's import_catalog.py
```

A gap disappears from the queue automatically once `catalog_overlay` has a value for it (scraped
or manually corrected via the UI) — no separate "resolved" bookkeeping needed.
