# IcyBox Stream Analyzer

A CLI tool that connects to the [IcyBox](https://www.icybox.io) activity stream, collects box-opening events in real time, and stores everything in a SQLite database for analysis. Includes a Flask dashboard for browsing the watch catalog, viewing analytics, and simulating box opens.

## What it does

- **Collects** live box-opening events via SSE (Server-Sent Events) or polling
- **Persists** events to a local JSONL file with deduplication
- **Builds a SQLite database** with watches, events, boxes, rarities, stated odds, and grail watch listings
- **Scrapes IcyBox website** for stated odds and grail watches, tracking changes over time
- **Downloads watch images** organized by price bucket
- **Dashboard** for browsing watches, viewing drop stats, analytics, and simulating box opens
- **SQL queries** for analysis: profit by tier, rarity drift, user P&L, and more

## Setup

```bash
# Collector (Node.js)
npm install
npm run build

# Tools + Dashboard (Python)
python3 -m venv .venv
source .venv/bin/activate
pip install flask playwright
python -m playwright install chromium
```

## Usage

### 1. Collect events

```bash
node dist/cli.js collect
```

Options:
- `--data-file <path>` — JSONL output path (default: `./icybox-data.jsonl`)
- `--mode <mode>` — `sse` (default) or `polling`
- `--interval <seconds>` — polling interval (default: 30)

### 2. Build the database

```bash
source .venv/bin/activate
python tools/build_db.py --output '/Volumes/Crucial X9/projects/icybox_stream'
```

### 3. Scrape stated odds and grail watches

```bash
python tools/scrape_boxes.py --output '/Volumes/Crucial X9/projects/icybox_stream'
```

### 4. Sync everything at once

```bash
python tools/sync_db.py --input ./icybox-data.jsonl --output '/Volumes/Crucial X9/projects/icybox_stream'
```

### 5. Browse the dashboard

```bash
.venv/bin/python web/dashboard/app.py \
  --db '/Volumes/Crucial X9/projects/icybox_stream/icybox.db' \
  --images '/Volumes/Crucial X9/projects/icybox_stream/images'
```

Open http://localhost:5000. See [web/README.md](web/README.md) for full dashboard docs.

### 6. Analyze with SQL

Open `icybox.db` in [DB Browser for SQLite](https://sqlitebrowser.org/) and run queries from `web/queries/`.

## Project Structure

```
src/                          # Node.js event collector
├── cli.ts
├── types.ts
└── collector/
    ├── sse-client.ts
    ├── polling-client.ts
    ├── event-parser.ts
    ├── deduplicator.ts
    ├── data-writer.ts
    └── backoff.ts

tools/                        # Python DB build + scraping tools
├── build_db.py
├── scrape_boxes.py
├── sync_db.py
└── build_site.py

web/                          # Dashboard, queries, static site
├── dashboard/                # Flask app
│   ├── app.py
│   ├── static/
│   ├── templates/
│   └── test_*.py
├── queries/                  # SQL analytics (loaded at runtime)
└── site/                     # Static site output
```

## Database Schema

| Table | Managed by | Description |
|-------|-----------|-------------|
| **events** | build_db | Every raw stream event |
| **watches** | build_db | Deduplicated watch catalog |
| **boxes** | build_db | Box tiers (discovered from events) |
| **rarities** | build_db | Rarity keys (discovered from events) |
| **box_pricing** | scrape_boxes | Versioned box prices |
| **stated_odds** | scrape_boxes | Advertised odds, versioned |
| **listed_watches** | scrape_boxes | Grail watches with delisting tracking |
| **user_watch_data** | dashboard | User-entered MSRP, market value, notes, etc. |
| **user_simulation** | dashboard | Simulated box opens |

See [tools/README.md](tools/README.md) for the full ER diagram.

## Tests

```bash
# Collector tests
npm test

# Dashboard tests
.venv/bin/python -m pytest web/dashboard/ -v
```

## License

GPL-3.0

## Disclaimer

*This project is not affiliated with, endorsed by, or associated with IcyBox or Infinite Edgers. It uses publicly available data for independent analysis.*
