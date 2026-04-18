Welcome to my vibecoded, overengineered solution to a simple question: what is the EV (Expected Value) of a wristwatch lootbox I got an ad for?

# IcyBox Stream Analyzer

A CLI tool that connects to the [IcyBox](https://www.icybox.io) activity stream, collects box-opening events in real time, and stores everything in a SQLite database for analysis.

## What it does

- **Collects** live box-opening events via SSE (Server-Sent Events) or polling
- **Persists** events to a local JSONL file with deduplication
- **Saves rejected events** to a separate file so nothing from the stream is ever lost
- **Builds a SQLite database** with watches, events, boxes, rarities, stated odds, and grail watch listings
- **Scrapes IcyBox website** for stated odds and grail watches, tracking changes over time
- **Downloads watch images** organized by price bucket
- **SQL queries** for analysis: profit by tier, rarity drift, user P&L, watch catalog, and more

## Setup

```bash
# Collector (Node.js)
npm install
npm run build

# Tools (Python)
python3 -m venv .venv
source .venv/bin/activate
pip install playwright
python -m playwright install chromium
```

## Usage

### 1. Collect events

Start the collector to stream live events into a local file:

```bash
node dist/cli.js collect
```

Options:
- `--data-file <path>` — JSONL output path (default: `./icybox-data.jsonl`)
- `--mode <mode>` — `sse` (default) or `polling`
- `--interval <seconds>` — polling interval (default: 30)

Press `Ctrl+C` to stop. Handles reconnection with exponential backoff and HTTP 429 rate limits.

### 2. Build the database

Ingest collected events into SQLite and download watch images:

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

### 5. Analyze with SQL

Open `icybox.db` in [DB Browser for SQLite](https://sqlitebrowser.org/) and run queries from the `queries/` folder.

## Database schema

| Table | Description |
|-------|-------------|
| **events** | Every raw stream event with all fields |
| **watches** | Deduplicated watch catalog (one row per unique watch) |
| **boxes** | Box tiers with names, slugs, current price, deprecation tracking |
| **rarities** | Rarity keys with full and short names |
| **box_pricing** | Versioned box prices with effective date ranges |
| **stated_odds** | Advertised odds from the website, versioned with effective dates |
| **listed_watches** | Grail watches from box pages, with delisting tracking |

Boxes and rarities are discovered automatically from events — no hardcoded lists. The scraper updates prices, odds, and grail listings from the website, versioning changes over time.

## Queries

Pre-built SQL queries in `queries/`:

| Query | Description |
|-------|-------------|
| `profit-by-tier.sql` | P&L breakdown per box tier (time-aware pricing) |
| `profit-total.sql` | Grand total across all boxes (time-aware pricing) |
| `rarity-odds-per-box.sql` | Observed drop rates per tier |
| `rarity-drift-by-period.sql` | Stated vs observed odds with drift per time period |
| `top-users.sql` | Leaderboard with per-tier breakdown |
| `user-loss.sql` | Per-event P&L with running total per user |
| `watch-drops-per-tier.sql` | Complete watch catalog with rarity and drop counts per tier |

## Data format

Events are stored as JSON Lines (`.jsonl`), one event per line:

```json
{
  "id": "abc123",
  "username": "player1",
  "platform": "web",
  "boxName": "Gold Box",
  "boxSlug": "gold-box",
  "itemName": "Diamond Watch",
  "itemValue": 150.50,
  "rarity": "chronograph",
  "rarityColor": "#FFD700",
  "itemImageUrl": "https://example.com/watch.png",
  "acquiredAt": "2024-01-15T10:30:00.000Z",
  "collectedAt": "2024-01-15T10:30:05.123Z"
}
```

Rejected events are saved to `*-rejected.jsonl` so nothing is ever discarded.

## Architecture

```
src/
├── cli.ts                    # CLI entry point (collector only)
├── types.ts                  # Shared types and interfaces
└── collector/
    ├── sse-client.ts         # SSE connection with backoff
    ├── polling-client.ts     # Polling alternative
    ├── event-parser.ts       # Event validation and parsing
    ├── deduplicator.ts       # In-memory ID deduplication
    ├── data-writer.ts        # JSONL append writer
    └── backoff.ts            # Exponential backoff calculator

tools/
├── build_db.py               # JSONL → SQLite ingestion + image downloads
├── scrape_boxes.py           # Website scraper for odds and grail watches
├── sync_db.py                # Runs build_db + scrape_boxes in sequence
└── jsonl_to_csv.py           # JSONL → CSV converter

queries/                      # Pre-built SQL queries for analysis
```

## Development

```bash
npm run build    # Compile TypeScript
npm test         # Run tests
```

## License

GPL-3.0

## Disclaimer

*This project is not affiliated with, endorsed by, or associated with IcyBox or Infinite Edgers. It uses publicly available data for independent analysis.*
