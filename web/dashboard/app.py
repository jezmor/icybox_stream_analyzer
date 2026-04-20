#!/usr/bin/env python3
"""
Watch Catalog Dashboard — Flask web application for browsing IcyBox watch data.

Usage:
    python dashboard/app.py [--db PATH] [--images PATH] [--port PORT]
"""

import argparse
import os
import random
import re
import sqlite3
import sys
from pathlib import Path

from flask import Flask, request, render_template, abort, send_from_directory, jsonify

# ── Flask App ──

app = Flask(__name__)


# ── CLI Argument Parsing ──

def parse_args(argv=None):
    """Parse command-line arguments for the dashboard."""
    parser = argparse.ArgumentParser(description="Watch Catalog Dashboard")
    parser.add_argument(
        "--db",
        default="./watch-catalog/icybox.db",
        help="Path to SQLite database (default: ./watch-catalog/icybox.db)",
    )
    parser.add_argument(
        "--images",
        default="./watch-catalog/images",
        help="Path to watch images directory (default: ./watch-catalog/images)",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=5000,
        help="Port to bind to (default: 5000)",
    )
    return parser.parse_args(argv)


def configure_app(args):
    """Validate paths and store configuration in app.config."""
    db_path = os.path.abspath(args.db)
    images_path = os.path.abspath(args.images)

    if not os.path.exists(db_path):
        print(f"Error: Database file not found: {db_path}", file=sys.stderr)
        sys.exit(1)

    if not os.path.isdir(images_path):
        print(f"Warning: Images directory not found: {images_path}", file=sys.stderr)

    app.config["DB_PATH"] = db_path
    app.config["IMAGES_PATH"] = images_path

    ensure_user_data_table(db_path)


# ── Helpers ──

def slugify(text: str) -> str:
    """Convert text to a URL-friendly slug. Matches slugify() in tools/build_db.py."""
    text = text.lower().strip()
    text = re.sub(r'[^\w\s-]', '', text)
    text = re.sub(r'[\s_]+', '-', text)
    text = re.sub(r'-+', '-', text)
    return text.strip('-')


def get_db() -> sqlite3.Connection:
    """Open a read-only SQLite connection to the configured database."""
    db_path = app.config["DB_PATH"]
    uri = f"file:{db_path}?mode=ro"
    conn = sqlite3.connect(uri, uri=True)
    conn.row_factory = sqlite3.Row
    return conn


def get_writable_db() -> sqlite3.Connection:
    """Open a writable SQLite connection to the configured database.

    Used only for user_watch_data operations. Does NOT use ?mode=ro.
    """
    db_path = app.config["DB_PATH"]
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


def ensure_user_data_table(db_path: str) -> None:
    """Create the user_watch_data table if it does not exist.

    Called once during configure_app() at startup.
    Also adds columns that may not exist yet (for upgrades).
    """
    conn = sqlite3.connect(db_path)
    try:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS user_watch_data (
                item_name TEXT PRIMARY KEY,
                msrp REAL,
                market_value REAL,
                notes TEXT,
                reference_number TEXT,
                market_value_source TEXT,
                manufacturer_url TEXT
            )
            """
        )
        # Add reference_number column if upgrading from older schema
        try:
            conn.execute("ALTER TABLE user_watch_data ADD COLUMN reference_number TEXT")
        except sqlite3.OperationalError:
            pass  # column already exists
        # Add market_value_source column if upgrading from older schema
        try:
            conn.execute("ALTER TABLE user_watch_data ADD COLUMN market_value_source TEXT")
        except sqlite3.OperationalError:
            pass  # column already exists
        try:
            conn.execute("ALTER TABLE user_watch_data ADD COLUMN manufacturer_url TEXT")
        except sqlite3.OperationalError:
            pass  # column already exists

        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS user_simulation (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                box_tier TEXT NOT NULL,
                item_name TEXT NOT NULL,
                item_value REAL NOT NULL,
                rarity TEXT NOT NULL,
                box_cost REAL NOT NULL,
                opened_at TEXT NOT NULL DEFAULT (datetime('now'))
            )
            """
        )
        conn.commit()
    finally:
        conn.close()


def validate_price_value(value) -> tuple:
    """Validate a price input (MSRP or Market Value).

    Returns (parsed_float, None) on success or (None, error_message) on failure.
    Accepts None or empty string to clear the value (returns (None, None)).
    Strips dollar signs and commas before parsing.
    Rejects non-numeric and negative values.
    """
    if value is None or value == "":
        return (None, None)

    # Strip $ and , so users can paste formatted values
    if isinstance(value, str):
        value = value.replace("$", "").replace(",", "").strip()
        if value == "":
            return (None, None)

    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return (None, "Value must be a non-negative number")

    if parsed < 0:
        return (None, "Value must be a non-negative number")

    return (parsed, None)


_UNSET = object()  # sentinel to distinguish "not provided" from "set to None"


def save_watch_user_data(writable_conn, item_name: str, msrp=_UNSET, market_value=_UNSET, notes=_UNSET, reference_number=_UNSET, market_value_source=_UNSET, manufacturer_url=_UNSET) -> dict:
    """Save user-managed data for a watch, merging with existing values.

    Only fields that are explicitly passed are updated. Fields left as _UNSET
    keep their current database value. Pass None or "" to clear a field.
    If all fields end up None, the row is deleted.
    Returns a dict of the final saved values.
    """
    # Read existing data first
    existing = writable_conn.execute(
        "SELECT msrp, market_value, notes, reference_number, market_value_source, manufacturer_url FROM user_watch_data WHERE item_name = ?",
        (item_name,),
    ).fetchone()

    if existing:
        cur_msrp = existing[0]
        cur_mv = existing[1]
        cur_notes = existing[2]
        cur_ref = existing[3]
        cur_mvsrc = existing[4]
        cur_mfg_url = existing[5]
    else:
        cur_msrp = None
        cur_mv = None
        cur_notes = None
        cur_ref = None
        cur_mvsrc = None
        cur_mfg_url = None

    # Merge: only override if the caller provided a value
    final_msrp = cur_msrp if msrp is _UNSET else msrp
    final_mv = cur_mv if market_value is _UNSET else market_value
    final_notes = cur_notes if notes is _UNSET else notes
    final_ref = cur_ref if reference_number is _UNSET else reference_number
    final_mvsrc = cur_mvsrc if market_value_source is _UNSET else market_value_source
    final_mfg_url = cur_mfg_url if manufacturer_url is _UNSET else manufacturer_url

    # Treat empty strings as None for clearing
    if final_msrp == "":
        final_msrp = None
    if final_mv == "":
        final_mv = None
    if final_notes == "":
        final_notes = None
    if final_ref == "":
        final_ref = None
    if final_mvsrc == "":
        final_mvsrc = None
    if final_mfg_url == "":
        final_mfg_url = None

    # If all fields are cleared, delete the row
    if final_msrp is None and final_mv is None and final_notes is None and final_ref is None and final_mvsrc is None and final_mfg_url is None:
        writable_conn.execute(
            "DELETE FROM user_watch_data WHERE item_name = ?",
            (item_name,),
        )
        writable_conn.commit()
        return {"item_name": item_name, "msrp": None, "market_value": None, "notes": None, "reference_number": None, "market_value_source": None, "manufacturer_url": None}

    writable_conn.execute(
        """
        INSERT OR REPLACE INTO user_watch_data (item_name, msrp, market_value, notes, reference_number, market_value_source, manufacturer_url)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (item_name, final_msrp, final_mv, final_notes, final_ref, final_mvsrc, final_mfg_url),
    )
    writable_conn.commit()
    return {"item_name": item_name, "msrp": final_msrp, "market_value": final_mv, "notes": final_notes, "reference_number": final_ref, "market_value_source": final_mvsrc, "manufacturer_url": final_mfg_url}


def get_watch_user_data(conn, item_name: str):
    """Retrieve user-managed data for a single watch from user_watch_data.

    Returns a dict with msrp, market_value, notes, reference_number or None if no row exists.
    """
    row = conn.execute(
        "SELECT msrp, market_value, notes, reference_number, market_value_source, manufacturer_url FROM user_watch_data WHERE item_name = ?",
        (item_name,),
    ).fetchone()

    if row is None:
        return None

    return {"msrp": row["msrp"], "market_value": row["market_value"], "notes": row["notes"], "reference_number": row["reference_number"], "market_value_source": row["market_value_source"], "manufacturer_url": row["manufacturer_url"]}


# ── Rarity Colors ──

RARITY_COLORS = {
    "quartz": "#9ca3af",
    "automatic": "#22c55e",
    "chronograph": "#3b82f6",
    "tourbillon": "#a855f7",
    "grand_tourbillon": "#ef4444",
    "grail": "#eab308",
}


# ── Template Filters ──

def format_money(value):
    """Format a numeric value as $1,234.56."""
    try:
        return f"${float(value):,.2f}"
    except (TypeError, ValueError):
        return value


def format_pct(value):
    """Format a numeric value as 12.34%."""
    try:
        return f"{float(value):.2f}%"
    except (TypeError, ValueError):
        return value


def rarity_color(rarity_key: str) -> str:
    """Return the hex color for a rarity key."""
    return RARITY_COLORS.get(rarity_key, "#6b7280")


MONEY_COLUMN_KEYWORDS = ("cost", "spent", "received", "loss", "profit", "net_gain", "total_in", "total_out", "pnl", "running_pnl", "paid", "value", "min_value", "max_value")
PCT_COLUMN_KEYWORDS = ("pct", "drift", "return")


def is_money_column(col_name: str) -> bool:
    """Check if a column name indicates monetary data."""
    col_lower = col_name.lower()
    return any(kw in col_lower for kw in MONEY_COLUMN_KEYWORDS)


def is_pct_column(col_name: str) -> bool:
    """Check if a column name indicates percentage data."""
    col_lower = col_name.lower()
    return any(kw in col_lower for kw in PCT_COLUMN_KEYWORDS)


app.jinja_env.filters["format_money"] = format_money
app.jinja_env.filters["format_pct"] = format_pct
app.jinja_env.filters["slugify"] = slugify
app.jinja_env.globals["rarity_color"] = rarity_color
app.jinja_env.globals["is_money_column"] = is_money_column
app.jinja_env.globals["is_pct_column"] = is_pct_column


# ── Analytics Queries ──

ANALYTICS_QUERIES = {
    "profit-by-tier":        {"title": "Profit by Tier",         "file": "profit-by-tier.sql",         "description": "P&L breakdown per box tier with time-aware pricing"},
    "rarity-drift-by-period":{"title": "Rarity Drift by Period", "file": "rarity-drift-by-period.sql", "description": "Stated vs observed odds with drift per time period"},
    "top-users":             {"title": "Top Users",              "file": "top-users.sql",              "description": "Leaderboard with per-tier breakdown"},
    "user-loss":             {"title": "User P&L",               "file": "user-loss.sql",              "description": "Per-event P&L with running total per user"},
    "watch-drops-per-tier":  {"title": "Watch Drops per Tier",   "file": "watch-drops-per-tier.sql",   "description": "Complete watch catalog with rarity and drop counts per tier"},
}


def load_sql_query(query_name: str) -> str:
    """Load a .sql file from the queries/ directory by query name.

    Looks up the filename in ANALYTICS_QUERIES and reads the file from
    the queries/ directory relative to the project root.
    """
    meta = ANALYTICS_QUERIES.get(query_name)
    if meta is None:
        raise ValueError(f"Unknown query: {query_name}")

    # queries/ directory is at the project root, one level up from dashboard/
    queries_dir = Path(__file__).resolve().parent.parent / "queries"
    sql_path = queries_dir / meta["file"]

    with open(sql_path, "r") as f:
        return f.read()


def execute_analytics_query(conn: sqlite3.Connection, query_name: str) -> tuple:
    """Execute a named analytics query and return (column_names, rows).

    Returns:
        A tuple of (list[str], list[tuple]) — column names and result rows.
    """
    sql = load_sql_query(query_name)
    cursor = conn.execute(sql)
    columns = [desc[0] for desc in cursor.description] if cursor.description else []
    rows = cursor.fetchall()
    return columns, rows


# ── Database Query Functions ──


def query_watches(conn, tier=None, rarity=None, search=None, sort="value-desc"):
    """Query watches with optional filters and sorting.

    LEFT JOINs user_watch_data to include msrp and market_value.
    Returns a list of dicts matching the CatalogWatch view model.
    """
    # Stream watches from events
    rows = conn.execute("""
        SELECT
            e.item_name,
            e.item_value,
            MAX(CASE WHEN e.box_tier = 'Bronze' THEN e.rarity END) AS bronze,
            MAX(CASE WHEN e.box_tier = 'Silver' THEN e.rarity END) AS silver,
            MAX(CASE WHEN e.box_tier = 'Gold' THEN e.rarity END) AS gold,
            MAX(CASE WHEN e.box_tier = 'Icy' THEN e.rarity END) AS icy,
            SUM(CASE WHEN e.box_tier = 'Bronze' THEN 1 ELSE 0 END) AS bronze_count,
            SUM(CASE WHEN e.box_tier = 'Silver' THEN 1 ELSE 0 END) AS silver_count,
            SUM(CASE WHEN e.box_tier = 'Gold' THEN 1 ELSE 0 END) AS gold_count,
            SUM(CASE WHEN e.box_tier = 'Icy' THEN 1 ELSE 0 END) AS icy_count,
            COUNT(*) AS total_drops,
            MIN(e.acquired_at) AS first_seen,
            w.image_path,
            ud.msrp,
            ud.market_value
        FROM events e
        LEFT JOIN watches w ON w.item_name = e.item_name
        LEFT JOIN user_watch_data ud ON ud.item_name = e.item_name
        GROUP BY e.item_name
    """).fetchall()

    watches = []
    for r in rows:
        watches.append({
            "name": r["item_name"],
            "value": r["item_value"],
            "slug": slugify(r["item_name"]),
            "image_path": r["image_path"] or "",
            "bronze": r["bronze"],
            "silver": r["silver"],
            "gold": r["gold"],
            "icy": r["icy"],
            "bronze_count": r["bronze_count"],
            "silver_count": r["silver_count"],
            "gold_count": r["gold_count"],
            "icy_count": r["icy_count"],
            "total_drops": r["total_drops"],
            "first_seen": r["first_seen"],
            "source": "stream",
            "msrp": r["msrp"],
            "market_value": r["market_value"],
        })

    # Add listed-only watches (grails not seen in stream)
    listed_rows = conn.execute("""
        SELECT lw.item_name, lw.item_value, lw.box_tier, lw.image_path,
               ud.msrp, ud.market_value
        FROM listed_watches lw
        LEFT JOIN user_watch_data ud ON ud.item_name = lw.item_name
        WHERE lw.listed = 1
          AND lw.item_name NOT IN (SELECT DISTINCT item_name FROM events)
    """).fetchall()

    grail_map = {}
    for r in listed_rows:
        name = r["item_name"]
        if name not in grail_map:
            grail_map[name] = {
                "name": name,
                "value": r["item_value"],
                "slug": slugify(name),
                "image_path": r["image_path"] or "",
                "bronze": None,
                "silver": None,
                "gold": None,
                "icy": None,
                "bronze_count": 0,
                "silver_count": 0,
                "gold_count": 0,
                "icy_count": 0,
                "total_drops": 0,
                "first_seen": None,
                "source": "listed",
                "msrp": r["msrp"],
                "market_value": r["market_value"],
            }
        tier_key = r["box_tier"].lower()
        if tier_key in ("bronze", "silver", "gold", "icy"):
            grail_map[name][tier_key] = "grail"

    watches.extend(grail_map.values())

    # Apply filters
    if tier:
        tier_key = tier.lower()
        watches = [w for w in watches if w.get(tier_key) is not None]

    if rarity:
        watches = [
            w for w in watches
            if any(w.get(t) == rarity for t in ("bronze", "silver", "gold", "icy"))
        ]

    if search:
        search_lower = search.lower()
        watches = [w for w in watches if search_lower in w["name"].lower()]

    # Apply sorting
    if sort == "value-desc":
        watches.sort(key=lambda w: w["value"], reverse=True)
    elif sort == "value-asc":
        watches.sort(key=lambda w: w["value"])
    elif sort == "drops-desc":
        watches.sort(key=lambda w: w["total_drops"], reverse=True)
    elif sort == "drops-asc":
        watches.sort(key=lambda w: w["total_drops"])
    elif sort == "newest":
        watches.sort(key=lambda w: w["first_seen"] or "", reverse=True)
    else:
        watches.sort(key=lambda w: w["value"], reverse=True)

    return watches


def query_watch_detail(conn, slug: str):
    """Query a single watch by slug.

    LEFT JOINs user_watch_data to include msrp, market_value, and notes.
    Returns a dict matching the WatchDetail view model, or None if not found.
    """
    # Try stream watches first
    rows = conn.execute("""
        SELECT
            e.item_name,
            e.item_value,
            e.box_tier,
            e.rarity,
            COUNT(*) AS drop_count,
            MIN(e.acquired_at) AS first_seen,
            MAX(e.acquired_at) AS last_seen
        FROM events e
        GROUP BY e.item_name, e.box_tier
    """).fetchall()

    # Group by item_name
    watch_tiers = {}
    for r in rows:
        name = r["item_name"]
        if slugify(name) != slug:
            continue
        if name not in watch_tiers:
            watch_tiers[name] = {
                "name": name,
                "value": r["item_value"],
                "tiers": [],
                "first_seen": r["first_seen"],
                "last_seen": r["last_seen"],
                "total_drops": 0,
            }
        entry = watch_tiers[name]
        entry["tiers"].append({
            "tier": r["box_tier"],
            "rarity": r["rarity"],
            "drop_count": r["drop_count"],
        })
        entry["total_drops"] += r["drop_count"]
        if r["first_seen"] and (entry["first_seen"] is None or r["first_seen"] < entry["first_seen"]):
            entry["first_seen"] = r["first_seen"]
        if r["last_seen"] and (entry["last_seen"] is None or r["last_seen"] > entry["last_seen"]):
            entry["last_seen"] = r["last_seen"]

    if watch_tiers:
        # Should be exactly one match
        name = list(watch_tiers.keys())[0]
        detail = watch_tiers[name]

        # Get image_path from watches table
        img_row = conn.execute(
            "SELECT image_path FROM watches WHERE item_name = ?", (name,)
        ).fetchone()
        image_path = img_row["image_path"] if img_row and img_row["image_path"] else ""

        # Calculate drop rates per tier
        for tier_info in detail["tiers"]:
            tier_total = conn.execute(
                "SELECT COUNT(*) AS cnt FROM events WHERE box_tier = ?",
                (tier_info["tier"],),
            ).fetchone()
            tier_total_opens = tier_total["cnt"] if tier_total else 0
            tier_info["tier_total_opens"] = tier_total_opens
            tier_info["drop_rate"] = (
                (tier_info["drop_count"] / tier_total_opens * 100)
                if tier_total_opens > 0
                else 0.0
            )

        # Get user data
        ud_row = conn.execute(
            "SELECT msrp, market_value, notes, reference_number, market_value_source, manufacturer_url FROM user_watch_data WHERE item_name = ?",
            (name,),
        ).fetchone()

        return {
            "name": name,
            "value": detail["value"],
            "slug": slug,
            "image_path": image_path,
            "tiers": detail["tiers"],
            "first_seen": detail["first_seen"],
            "last_seen": detail["last_seen"],
            "total_drops": detail["total_drops"],
            "is_listed_only": False,
            "msrp": ud_row["msrp"] if ud_row else None,
            "market_value": ud_row["market_value"] if ud_row else None,
            "notes": ud_row["notes"] if ud_row else None,
            "reference_number": ud_row["reference_number"] if ud_row else None,
            "market_value_source": ud_row["market_value_source"] if ud_row else None,
            "manufacturer_url": ud_row["manufacturer_url"] if ud_row else None,
        }

    # Try listed-only watches
    listed_rows = conn.execute("""
        SELECT lw.item_name, lw.item_value, lw.box_tier, lw.image_path
        FROM listed_watches lw
        WHERE lw.listed = 1
          AND lw.item_name NOT IN (SELECT DISTINCT item_name FROM events)
    """).fetchall()

    listed_match = {}
    for r in listed_rows:
        name = r["item_name"]
        if slugify(name) != slug:
            continue
        if name not in listed_match:
            listed_match[name] = {
                "name": name,
                "value": r["item_value"],
                "image_path": r["image_path"] or "",
                "tiers": [],
            }
        listed_match[name]["tiers"].append({
            "tier": r["box_tier"],
            "rarity": "grail",
            "drop_count": 0,
            "drop_rate": 0.0,
            "tier_total_opens": 0,
        })

    if listed_match:
        name = list(listed_match.keys())[0]
        detail = listed_match[name]

        # Get user data
        ud_row = conn.execute(
            "SELECT msrp, market_value, notes, reference_number, market_value_source, manufacturer_url FROM user_watch_data WHERE item_name = ?",
            (name,),
        ).fetchone()

        return {
            "name": name,
            "value": detail["value"],
            "slug": slug,
            "image_path": detail["image_path"],
            "tiers": detail["tiers"],
            "first_seen": None,
            "last_seen": None,
            "total_drops": 0,
            "is_listed_only": True,
            "msrp": ud_row["msrp"] if ud_row else None,
            "market_value": ud_row["market_value"] if ud_row else None,
            "notes": ud_row["notes"] if ud_row else None,
            "reference_number": ud_row["reference_number"] if ud_row else None,
            "market_value_source": ud_row["market_value_source"] if ud_row else None,
            "manufacturer_url": ud_row["manufacturer_url"] if ud_row else None,
        }

    return None


def query_box_page(conn, tier: str):
    """Query all data for a box tier page.

    LEFT JOINs user_watch_data to include msrp and market_value per watch.
    Returns a dict matching the BoxPageData view model, or None if tier not found.
    """
    # Verify tier exists
    box_row = conn.execute(
        "SELECT box_name, box_tier FROM boxes WHERE box_tier = ?", (tier,)
    ).fetchone()
    if box_row is None:
        return None

    box_name = box_row["box_name"]

    # Get current box price from box_pricing
    price_row = conn.execute(
        "SELECT cost FROM box_pricing WHERE box_tier = ? AND effective_until IS NULL",
        (tier,),
    ).fetchone()
    box_price = price_row["cost"] if price_row else None

    # Get total opens for this tier
    total_row = conn.execute(
        "SELECT COUNT(*) AS cnt FROM events WHERE box_tier = ?", (tier,)
    ).fetchone()
    total_opens = total_row["cnt"] if total_row else 0

    # Get stated odds (current, not expired)
    odds_rows = conn.execute("""
        SELECT rarity_key, rarity_label, odds_pct, min_value, max_value
        FROM stated_odds
        WHERE box_tier = ? AND effective_until IS NULL
        ORDER BY min_value ASC
    """, (tier,)).fetchall()

    stated_odds = [
        {
            "rarity_key": r["rarity_key"],
            "rarity_label": r["rarity_label"],
            "odds_pct": r["odds_pct"],
            "min_value": r["min_value"],
            "max_value": r["max_value"],
        }
        for r in odds_rows
    ]

    # Get watches dropped in this tier, grouped by rarity
    watch_rows = conn.execute("""
        SELECT
            e.item_name,
            e.item_value,
            e.rarity,
            COUNT(*) AS drop_count,
            w.image_path,
            ud.msrp,
            ud.market_value
        FROM events e
        LEFT JOIN watches w ON w.item_name = e.item_name
        LEFT JOIN user_watch_data ud ON ud.item_name = e.item_name
        WHERE e.box_tier = ?
        GROUP BY e.item_name
        ORDER BY e.rarity, drop_count DESC
    """, (tier,)).fetchall()

    rarity_groups = {}
    for r in watch_rows:
        rarity_key = r["rarity"]
        if rarity_key not in rarity_groups:
            rarity_groups[rarity_key] = []
        drop_rate = (r["drop_count"] / total_opens * 100) if total_opens > 0 else 0.0
        rarity_groups[rarity_key].append({
            "name": r["item_name"],
            "value": r["item_value"],
            "slug": slugify(r["item_name"]),
            "image_path": r["image_path"] or "",
            "drop_count": r["drop_count"],
            "drop_rate": drop_rate,
            "msrp": r["msrp"],
            "market_value": r["market_value"],
        })

    # Get listed-only grail watches for this tier
    listed_rows = conn.execute("""
        SELECT lw.item_name, lw.item_value, lw.image_path,
               ud.msrp, ud.market_value
        FROM listed_watches lw
        LEFT JOIN user_watch_data ud ON ud.item_name = lw.item_name
        WHERE lw.box_tier = ? AND lw.listed = 1
          AND lw.item_name NOT IN (
              SELECT DISTINCT item_name FROM events WHERE box_tier = ?
          )
    """, (tier, tier)).fetchall()

    listed_only = [
        {
            "name": r["item_name"],
            "value": r["item_value"],
            "slug": slugify(r["item_name"]),
            "image_path": r["image_path"] or "",
            "drop_count": 0,
            "drop_rate": 0.0,
            "msrp": r["msrp"],
            "market_value": r["market_value"],
        }
        for r in listed_rows
    ]

    return {
        "tier": tier,
        "box_name": box_name,
        "box_price": box_price,
        "total_opens": total_opens,
        "stated_odds": stated_odds,
        "rarity_groups": rarity_groups,
        "listed_only": listed_only,
    }


def query_stats(conn):
    """Summary stats: total watches (distinct from events), events count, users count."""
    total_watches = conn.execute(
        "SELECT COUNT(DISTINCT item_name) FROM events"
    ).fetchone()[0]
    total_events = conn.execute("SELECT COUNT(*) FROM events").fetchone()[0]
    total_users = conn.execute(
        "SELECT COUNT(DISTINCT username) FROM events"
    ).fetchone()[0]
    return {"watches": total_watches, "events": total_events, "users": total_users}


def get_available_tiers(conn):
    """Get non-deprecated box tier names, ordered by current box price ascending."""
    rows = conn.execute(
        """
        SELECT b.box_tier
        FROM boxes b
        LEFT JOIN box_pricing bp
          ON bp.box_tier = b.box_tier AND bp.effective_until IS NULL
        WHERE b.deprecated_at IS NULL
        ORDER BY COALESCE(bp.cost, 0) ASC
        """
    ).fetchall()
    return [r["box_tier"] for r in rows]


# ── Simulation Helpers ──


def simulate_box_open(conn, tier: str):
    """Simulate opening a box for the given tier.

    1. Get stated odds for the tier (current, effective_until IS NULL)
    2. Roll a random rarity using the odds as weights
    3. Get all watches that have been observed in that tier+rarity from events,
       PLUS listed watches for that tier
    4. Pick a random watch
    5. Return dict with: item_name, item_value, rarity, box_cost, image_path, tier

    Uses random.choices() with odds_pct as weights for rarity selection.
    Returns None if tier has no stated odds.
    """
    # Get stated odds for the tier
    odds_rows = conn.execute(
        """
        SELECT rarity_key, odds_pct
        FROM stated_odds
        WHERE box_tier = ? AND effective_until IS NULL
        ORDER BY min_value ASC
        """,
        (tier,),
    ).fetchall()

    if not odds_rows:
        return None

    rarity_keys = [r["rarity_key"] for r in odds_rows]
    odds_pcts = [r["odds_pct"] for r in odds_rows]

    # Roll a rarity
    rolled_rarity = random.choices(rarity_keys, weights=odds_pcts, k=1)[0]

    # Get candidate watches from events in this tier+rarity
    # Listed watches (grails) are only included when "grail" is rolled
    if rolled_rarity == "grail":
        candidates = conn.execute(
            """
            SELECT DISTINCT e.item_name, e.item_value, COALESCE(w.image_path, '') AS image_path
            FROM events e
            LEFT JOIN watches w ON w.item_name = e.item_name
            WHERE e.box_tier = ? AND e.rarity = 'grail'
            UNION
            SELECT lw.item_name, lw.item_value, COALESCE(lw.image_path, '') AS image_path
            FROM listed_watches lw
            WHERE lw.box_tier = ? AND lw.listed = 1
              AND lw.item_name NOT IN (
                  SELECT DISTINCT item_name FROM events WHERE box_tier = ?
              )
            """,
            (tier, tier, tier),
        ).fetchall()
    else:
        candidates = conn.execute(
            """
            SELECT DISTINCT e.item_name, e.item_value, COALESCE(w.image_path, '') AS image_path
            FROM events e
            LEFT JOIN watches w ON w.item_name = e.item_name
            WHERE e.box_tier = ? AND e.rarity = ?
            """,
            (tier, rolled_rarity),
        ).fetchall()

    if not candidates:
        return None

    pick = random.choice(candidates)

    # Get box cost
    price_row = conn.execute(
        "SELECT cost FROM box_pricing WHERE box_tier = ? AND effective_until IS NULL",
        (tier,),
    ).fetchone()
    box_cost = price_row["cost"] if price_row else 0.0

    return {
        "item_name": pick["item_name"],
        "item_value": pick["item_value"],
        "rarity": rolled_rarity,
        "box_cost": box_cost,
        "image_path": pick["image_path"],
        "tier": tier,
    }


def get_simulation_collection(conn):
    """Get all simulated opens, ordered by opened_at DESC.

    Returns list of dicts with: id, box_tier, item_name, item_value, rarity,
    box_cost, opened_at, image_path.
    Joins against watches and listed_watches to get image_path.
    """
    rows = conn.execute(
        """
        SELECT
            s.id, s.box_tier, s.item_name, s.item_value, s.rarity,
            s.box_cost, s.opened_at,
            COALESCE(w.image_path, lw_img.image_path, '') AS image_path
        FROM user_simulation s
        LEFT JOIN watches w ON w.item_name = s.item_name
        LEFT JOIN (
            SELECT item_name, image_path
            FROM listed_watches
            WHERE listed = 1
            GROUP BY item_name
        ) lw_img ON lw_img.item_name = s.item_name
        ORDER BY s.opened_at DESC
        """
    ).fetchall()

    return [
        {
            "id": r["id"],
            "box_tier": r["box_tier"],
            "item_name": r["item_name"],
            "item_value": r["item_value"],
            "rarity": r["rarity"],
            "box_cost": r["box_cost"],
            "opened_at": r["opened_at"],
            "image_path": r["image_path"],
        }
        for r in rows
    ]


def get_simulation_stats(conn):
    """Get simulation stats: total_opens, total_spent, total_value, net_gain_loss."""
    row = conn.execute(
        """
        SELECT
            COUNT(*) AS total_opens,
            COALESCE(SUM(box_cost), 0) AS total_spent,
            COALESCE(SUM(item_value), 0) AS total_value
        FROM user_simulation
        """
    ).fetchone()

    total_opens = row["total_opens"]
    total_spent = row["total_spent"]
    total_value = row["total_value"]

    return {
        "total_opens": total_opens,
        "total_spent": total_spent,
        "total_value": total_value,
        "net_gain_loss": total_value - total_spent,
    }


# ── Route Handlers ──


@app.route("/")
def catalog():
    """GET / — Watch catalog grid with filters and sorting."""
    tier = request.args.get("tier")
    rarity = request.args.get("rarity")
    search = request.args.get("search")
    sort = request.args.get("sort", "value-desc")

    conn = get_db()
    try:
        watches = query_watches(conn, tier=tier, rarity=rarity, search=search, sort=sort)
        stats = query_stats(conn)
        tiers = get_available_tiers(conn)
    finally:
        conn.close()

    return render_template(
        "catalog.html",
        watches=watches,
        stats=stats,
        filters={"tier": tier, "rarity": rarity, "search": search, "sort": sort},
        tiers=tiers,
        analytics_queries=ANALYTICS_QUERIES,
    )


@app.route("/watch/<slug>")
def watch_detail(slug):
    """GET /watch/<slug> — Single watch detail page."""
    conn = get_db()
    try:
        watch = query_watch_detail(conn, slug)
        if watch is None:
            abort(404)
        tiers = get_available_tiers(conn)
    finally:
        conn.close()

    return render_template(
        "watch.html",
        watch=watch,
        tiers=tiers,
        analytics_queries=ANALYTICS_QUERIES,
    )


@app.route("/box/<tier>")
def box_page(tier):
    """GET /box/<tier> — Box tier page with drop rate visualizations."""
    conn = get_db()
    try:
        data = query_box_page(conn, tier)
        if data is None:
            abort(404)
        tiers = get_available_tiers(conn)
    finally:
        conn.close()

    return render_template(
        "box.html",
        data=data,
        tiers=tiers,
        analytics_queries=ANALYTICS_QUERIES,
    )


@app.route("/analytics/<query_name>")
def analytics(query_name):
    """GET /analytics/<query_name> — Analytics query results page."""
    if query_name not in ANALYTICS_QUERIES:
        abort(404)

    meta = ANALYTICS_QUERIES[query_name]

    conn = get_db()
    try:
        columns, rows = execute_analytics_query(conn, query_name)
        tiers = get_available_tiers(conn)
    finally:
        conn.close()

    return render_template(
        "analytics.html",
        query_name=query_name,
        title=meta["title"],
        description=meta["description"],
        columns=columns,
        rows=rows,
        tiers=tiers,
        analytics_queries=ANALYTICS_QUERIES,
    )


@app.route("/simulate")
def simulate():
    """GET /simulate — Show the simulator page with collection."""
    conn = get_db()
    try:
        tiers = get_available_tiers(conn)
        collection = get_simulation_collection(conn)
        stats = get_simulation_stats(conn)
    finally:
        conn.close()

    return render_template(
        "simulate.html",
        tiers=tiers,
        collection=collection,
        stats=stats,
        analytics_queries=ANALYTICS_QUERIES,
    )


@app.route("/api/simulate/open", methods=["POST"])
def simulate_open():
    """POST /api/simulate/open — Open a box. JSON body: {"tier": "Gold"}"""
    try:
        data = request.get_json(force=True)
    except Exception:
        return jsonify({"ok": False, "error": "Invalid JSON"}), 400

    if data is None:
        return jsonify({"ok": False, "error": "Invalid JSON"}), 400

    tier = data.get("tier")
    if not tier:
        return jsonify({"ok": False, "error": "Missing tier"}), 400

    conn = get_db()
    try:
        result = simulate_box_open(conn, tier)
    finally:
        conn.close()

    if result is None:
        return jsonify({"ok": False, "error": f"No odds data for tier: {tier}"}), 400

    # Save to user_simulation
    writable_conn = get_writable_db()
    try:
        writable_conn.execute(
            """
            INSERT INTO user_simulation (box_tier, item_name, item_value, rarity, box_cost)
            VALUES (?, ?, ?, ?, ?)
            """,
            (result["tier"], result["item_name"], result["item_value"], result["rarity"], result["box_cost"]),
        )
        writable_conn.commit()

        # Get the inserted row id
        row_id = writable_conn.execute("SELECT last_insert_rowid()").fetchone()[0]

        # Get updated stats
        stats = get_simulation_stats(writable_conn)
    finally:
        writable_conn.close()

    return jsonify({
        "ok": True,
        "id": row_id,
        "item_name": result["item_name"],
        "item_value": result["item_value"],
        "rarity": result["rarity"],
        "box_cost": result["box_cost"],
        "image_path": result["image_path"],
        "tier": result["tier"],
        "slug": slugify(result["item_name"]),
        "stats": stats,
    })


@app.route("/api/simulate/discard", methods=["POST"])
def simulate_discard():
    """POST /api/simulate/discard — Discard a watch. JSON body: {"id": 123}"""
    try:
        data = request.get_json(force=True)
    except Exception:
        return jsonify({"ok": False, "error": "Invalid JSON"}), 400

    if data is None:
        return jsonify({"ok": False, "error": "Invalid JSON"}), 400

    sim_id = data.get("id")
    if sim_id is None:
        return jsonify({"ok": False, "error": "Missing id"}), 400

    writable_conn = get_writable_db()
    try:
        writable_conn.execute("DELETE FROM user_simulation WHERE id = ?", (sim_id,))
        writable_conn.commit()
        stats = get_simulation_stats(writable_conn)
    finally:
        writable_conn.close()

    return jsonify({"ok": True, "stats": stats})


@app.route("/api/simulate/reset", methods=["POST"])
def simulate_reset():
    """POST /api/simulate/reset — Clear all simulation data."""
    writable_conn = get_writable_db()
    try:
        writable_conn.execute("DELETE FROM user_simulation")
        writable_conn.commit()
    finally:
        writable_conn.close()

    return jsonify({
        "ok": True,
        "stats": {
            "total_opens": 0,
            "total_spent": 0,
            "total_value": 0,
            "net_gain_loss": 0,
        },
    })


@app.route("/images/<path:filepath>")
def serve_image(filepath):
    """GET /images/<path:filepath> — Serve watch images from configured directory."""
    return send_from_directory(app.config["IMAGES_PATH"], filepath)


@app.route("/api/watch/<slug>/user-data", methods=["POST"])
def save_user_data(slug):
    """POST /api/watch/<slug>/user-data — Save MSRP, Market Value, and/or Notes."""
    # Parse JSON body
    try:
        data = request.get_json(force=True)
    except Exception:
        return jsonify({"ok": False, "error": "Invalid JSON"}), 400

    if data is None:
        return jsonify({"ok": False, "error": "Invalid JSON"}), 400

    # Resolve slug to item_name
    conn = get_db()
    try:
        # Check stream watches (events table)
        rows = conn.execute("SELECT DISTINCT item_name FROM events").fetchall()
        item_name = None
        for r in rows:
            if slugify(r["item_name"]) == slug:
                item_name = r["item_name"]
                break

        # Check listed watches if not found in events
        if item_name is None:
            listed_rows = conn.execute(
                "SELECT DISTINCT item_name FROM listed_watches WHERE listed = 1"
            ).fetchall()
            for r in listed_rows:
                if slugify(r["item_name"]) == slug:
                    item_name = r["item_name"]
                    break
    finally:
        conn.close()

    if item_name is None:
        return jsonify({"ok": False, "error": "Watch not found"}), 404

    # Extract fields from request — use _UNSET for fields not provided
    msrp = data.get("msrp", _UNSET)
    market_value = data.get("market_value", _UNSET)
    notes = data.get("notes", _UNSET)
    reference_number = data.get("reference_number", _UNSET)
    market_value_source = data.get("market_value_source", _UNSET)
    manufacturer_url = data.get("manufacturer_url", _UNSET)

    # Validate MSRP if provided
    if msrp is not _UNSET:
        msrp_val, msrp_err = validate_price_value(msrp)
        if msrp_err:
            return jsonify({"ok": False, "error": f"MSRP: {msrp_err}"}), 400
    else:
        msrp_val = _UNSET

    # Validate Market Value if provided
    if market_value is not _UNSET:
        mv_val, mv_err = validate_price_value(market_value)
        if mv_err:
            return jsonify({"ok": False, "error": f"Market Value: {mv_err}"}), 400
    else:
        mv_val = _UNSET

    # Save to database
    writable_conn = get_writable_db()
    try:
        result = save_watch_user_data(writable_conn, item_name, msrp=msrp_val, market_value=mv_val, notes=notes, reference_number=reference_number, market_value_source=market_value_source, manufacturer_url=manufacturer_url)
    finally:
        writable_conn.close()

    return jsonify({
        "ok": True,
        "item_name": result["item_name"],
        "msrp": result["msrp"],
        "market_value": result["market_value"],
        "notes": result["notes"],
        "reference_number": result["reference_number"],
        "market_value_source": result["market_value_source"],
        "manufacturer_url": result["manufacturer_url"],
    })


# ── Entry Point ──

if __name__ == "__main__":
    args = parse_args()
    configure_app(args)
    app.run(host="127.0.0.1", port=args.port, debug=True)
