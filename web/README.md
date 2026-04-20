# Web

Flask dashboard and SQL analytics for browsing IcyBox watch data.

## Structure

```
web/
├── dashboard/          Flask app, templates, static CSS, tests
│   ├── app.py          Single entry point
│   ├── static/         CSS
│   ├── templates/      Jinja2 templates
│   ├── test_helpers.py
│   └── test_queries.py
├── queries/            SQL analytics queries (loaded at runtime)
└── site/               Static site output (from tools/build_site.py)
```

## Quick Start

Requires Flask (already in the venv):

```bash
.venv/bin/python web/dashboard/app.py \
  --db '/Volumes/Crucial X9/projects/icybox_stream/icybox.db' \
  --images '/Volumes/Crucial X9/projects/icybox_stream/images'
```

Then open http://localhost:5000.

### CLI Options

| Flag | Default | Description |
|------|---------|-------------|
| `--db` | `./watch-catalog/icybox.db` | Path to SQLite database |
| `--images` | `./watch-catalog/images` | Path to watch images directory |
| `--port` | `5000` | Port to bind to |

## Pages

### Watch Catalog (`/`)

Filterable, sortable card grid of all watches. Filter by box tier, rarity, or text search. Sort by value, drop count, or newest. Shows MSRP and market value when entered.

### Watch Detail (`/watch/<slug>`)

Per-watch page with drop statistics by tier, image, and user-editable fields:

- **MSRP** and **Market Value** (with source: eBay, Chrono24, StockX, etc.)
- **Reference Number**
- **Manufacturer URL** (clickable link to brand page)
- **Notes** (free text)

All saved via AJAX to a `user_watch_data` table — pipeline data stays read-only.

### Box Tier Pages (`/box/<tier>`)

Watches grouped by rarity with collapsible sections, search, sort, and percentage bars. Shows stated odds, box price, total opens, and thumbnails.

### Analytics (`/analytics/<query>`)

Formatted tables from the SQL queries in `web/queries/`:

| Query | Description |
|-------|-------------|
| `profit-by-tier` | P&L per box tier with totals row |
| `rarity-drift-by-period` | Stated vs observed odds with drift |
| `top-users` | Leaderboard with per-tier breakdown |
| `user-loss` | Per-event P&L with running total |
| `watch-drops-per-tier` | Full catalog with drop counts |

User-related pages have a client-side search bar.

### Box Simulator (`/simulate`)

Pick a tier, open boxes. Uses real stated odds to roll rarity, then picks a random watch. Tracks your collection with running stats (spent, value, net gain/loss). Discard individual watches or reset all.

## Database

The dashboard reads pipeline tables (`watches`, `events`, `boxes`, etc.) through a **read-only** connection. User-managed data uses a separate writable connection and two dashboard-owned tables:

### `user_watch_data`

Stores MSRP, market value, notes, reference number, manufacturer URL, and market value source per watch. Auto-created on startup. Pipeline tools don't touch this table.

### `user_simulation`

Stores simulated box opens for the simulator. Auto-created on startup.

## Tests

```bash
.venv/bin/python -m pytest web/dashboard/ -v
```

81 tests covering query functions, helper functions, validation, and API endpoints.
