# Tools

Python scripts for building and maintaining the IcyBox SQLite database.

## Setup

These scripts require a Python virtual environment:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install playwright
python -m playwright install chromium
```

Always activate the venv before running tools:

```bash
source .venv/bin/activate
```

## build_db.py

Ingests `icybox-data.jsonl` into a unified SQLite database (`icybox.db`). Creates tables for boxes, rarities, watches (deduplicated catalog), and events (every raw stream event). Downloads watch images organized by price bucket.

Re-runnable — new events and watches are added, existing ones are skipped.

```bash
# Default (writes to ./watch-catalog/)
python tools/build_db.py

# External drive
python tools/build_db.py --output '/Volumes/Crucial X9/projects/icybox_stream'

# Custom input file
python tools/build_db.py --input ./icybox-data.jsonl --output ./watch-catalog
```

### Database schema

- **boxes** — box tiers with names, slugs, current price, `deprecated_at`, `first_seen_at` (discovered from events)
- **rarities** — rarity keys with full and short names (discovered from events + website)
- **watches** — one row per unique watch (name, value, image path)
- **events** — every stream event with all fields
- **box_pricing** — versioned box prices with `effective_from` / `effective_until` dates
- **stated_odds** — advertised odds from the website, versioned with effective dates
- **listed_watches** — grail watches from box pages, with `delisted_at` tracking

### Rebuild from scratch

Delete the output folder and re-run:

```bash
rm -rf ./watch-catalog
python tools/build_db.py
```

## scrape_boxes.py

Scrapes the IcyBox website for stated odds, value ranges, and grail watch listings. Requires Playwright for JavaScript rendering. Blocks the SSE activity stream to speed up page loads.

Adds tables to `icybox.db`:

- **box_pricing** — versioned box prices with `effective_from` / `effective_until` dates
- **stated_odds** — advertised rarity percentages and value ranges per box, versioned with effective dates. If odds change between scrapes, the old row is closed and a new one is inserted — full history is preserved.
- **listed_watches** — grail watches shown on each box page, with `delisted_at` tracking

Discovers boxes dynamically from the database — no hardcoded list. New boxes from the stream get scraped automatically. If a box page 404s, it's marked as deprecated.

```bash
# Must run build_db.py first to create the database
python tools/scrape_boxes.py --output '/Volumes/Crucial X9/projects/icybox_stream'
```

Re-run to detect changes — odds changes are logged with `⚠ CHANGED` in the output.

## sync_db.py

Runs `build_db.py` then `scrape_boxes.py` in sequence. One command to update everything.

```bash
python tools/sync_db.py --input ./icybox-data.jsonl --output '/Volumes/Crucial X9/projects/icybox_stream'
```

Can be set up as a cron job for automated syncing (e.g. on a Raspberry Pi):

```bash
crontab -e
0 */12 * * * cd /path/to/icybox_stream && .venv/bin/python tools/sync_db.py --input ./icybox-data.jsonl --output /path/to/output >> sync.log 2>&1
```

## jsonl_to_csv.py

Simple converter from JSONL to CSV format.

```bash
python tools/jsonl_to_csv.py
python tools/jsonl_to_csv.py input.jsonl output.csv
```
