#!/usr/bin/env python3
"""
Build the unified IcyBox SQLite database from icybox-data.jsonl.

Creates a single icybox.db with tables: boxes, rarities, watches, events.
Downloads watch images locally. Re-runnable — adds new data on each run.

Usage:
  python3 tools/build_db.py
  python3 tools/build_db.py --input icybox-data.jsonl --output ./watch-catalog
  python3 tools/build_db.py --output '/Volumes/Crucial X9/projects/icybox_stream'
"""

import argparse
import json
import os
import re
import sqlite3
import sys
import time
import urllib.request
import urllib.error
from pathlib import Path


# ── Known data ──

KNOWN_BOXES = {
    'Bronze': {'box_name': 'Bronze Box', 'box_slug': 'bronze-box', 'cost': 50},
    'Silver': {'box_name': 'Silver Box', 'box_slug': 'silver-box', 'cost': 100},
    'Gold':   {'box_name': 'Gold Box',   'box_slug': 'gold-box',   'cost': 500},
    'Icy':    {'box_name': 'Ice Box',    'box_slug': 'ice-box',    'cost': 1000},
}

KNOWN_RARITIES = {
    'quartz':            {'full_name': 'Quartz',            'short_name': 'Quartz'},
    'automatic':         {'full_name': 'Automatic',         'short_name': 'Auto'},
    'chronograph':       {'full_name': 'Chronograph',       'short_name': 'Chrono'},
    'tourbillon':        {'full_name': 'Tourbillon',        'short_name': 'Tourbillon'},
    'grand':             {'full_name': 'Grand Tourbillon',  'short_name': 'Grand'},
    'grail':             {'full_name': 'Grail',             'short_name': 'Grail'},
}


# ── Helpers ──

def slugify(text: str) -> str:
    text = text.lower().strip()
    text = re.sub(r'[^\w\s-]', '', text)
    text = re.sub(r'[\s_]+', '-', text)
    text = re.sub(r'-+', '-', text)
    return text.strip('-')


def extract_tier(box_name: str) -> str:
    tier = re.sub(r'\s*Box$', '', box_name, flags=re.IGNORECASE).strip()
    if tier == 'Ice':
        tier = 'Icy'
    return tier


def price_bucket(value: float) -> str:
    if value < 100:
        return '$0-$100'
    elif value < 1000:
        return '$100-$1000'
    elif value < 10000:
        return '$1000-$10000'
    elif value < 100000:
        return '$10000-$100000'
    else:
        return '$100000+'


def get_image_ext(url: str) -> str:
    path = url.split('?')[0]
    ext = os.path.splitext(path)[1].lower()
    return ext if ext in ('.png', '.jpg', '.jpeg', '.gif', '.webp', '.svg') else '.png'


def download_image(url: str, dest: str) -> bool:
    if not url or os.path.exists(dest):
        return os.path.exists(dest)
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    try:
        req = urllib.request.Request(url, headers={
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) '
                          'AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4 Safari/605.1.15'
        })
        with urllib.request.urlopen(req, timeout=15) as resp:
            with open(dest, 'wb') as f:
                f.write(resp.read())
        return True
    except (urllib.error.URLError, OSError, TimeoutError) as e:
        print(f'  [warn] Failed to download {url}: {e}')
        return False


# ── Database ──

def init_db(db_path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS boxes (
            box_tier TEXT PRIMARY KEY,
            box_name TEXT NOT NULL,
            box_slug TEXT DEFAULT '',
            cost REAL
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS rarities (
            rarity_key TEXT PRIMARY KEY,
            full_name TEXT NOT NULL,
            short_name TEXT NOT NULL
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS watches (
            item_name TEXT PRIMARY KEY,
            item_value REAL NOT NULL,
            rarity_color TEXT DEFAULT '',
            image_url TEXT DEFAULT '',
            image_path TEXT DEFAULT ''
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS events (
            id TEXT PRIMARY KEY,
            username TEXT NOT NULL,
            platform TEXT DEFAULT '',
            box_name TEXT NOT NULL,
            box_tier TEXT NOT NULL REFERENCES boxes(box_tier),
            box_slug TEXT DEFAULT '',
            item_name TEXT NOT NULL REFERENCES watches(item_name),
            item_value REAL NOT NULL,
            rarity TEXT NOT NULL REFERENCES rarities(rarity_key),
            rarity_color TEXT DEFAULT '',
            item_image_url TEXT DEFAULT '',
            acquired_at TEXT NOT NULL,
            collected_at TEXT NOT NULL
        )
    """)

    conn.execute("CREATE INDEX IF NOT EXISTS idx_events_box_tier ON events(box_tier)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_events_rarity ON events(rarity)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_events_username ON events(username)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_events_item_name ON events(item_name)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_events_acquired_at ON events(acquired_at)")

    # Seed known boxes
    for tier, info in KNOWN_BOXES.items():
        conn.execute(
            "INSERT OR IGNORE INTO boxes (box_tier, box_name, box_slug, cost) VALUES (?, ?, ?, ?)",
            (tier, info['box_name'], info['box_slug'], info['cost'])
        )

    # Seed known rarities
    for key, info in KNOWN_RARITIES.items():
        conn.execute(
            "INSERT OR IGNORE INTO rarities (rarity_key, full_name, short_name) VALUES (?, ?, ?)",
            (key, info['full_name'], info['short_name'])
        )

    conn.commit()
    return conn


def ensure_box(conn: sqlite3.Connection, box_tier: str, box_name: str, box_slug: str):
    row = conn.execute("SELECT 1 FROM boxes WHERE box_tier = ?", (box_tier,)).fetchone()
    if not row:
        conn.execute(
            "INSERT INTO boxes (box_tier, box_name, box_slug, cost) VALUES (?, ?, ?, NULL)",
            (box_tier, box_name, box_slug)
        )


def ensure_rarity(conn: sqlite3.Connection, rarity_key: str):
    row = conn.execute("SELECT 1 FROM rarities WHERE rarity_key = ?", (rarity_key,)).fetchone()
    if not row:
        full_name = rarity_key.replace('_', ' ').title()
        short_name = full_name.split()[-1] if ' ' in full_name else full_name
        conn.execute(
            "INSERT INTO rarities (rarity_key, full_name, short_name) VALUES (?, ?, ?)",
            (rarity_key, full_name, short_name)
        )


# ── Processing ──

def process(input_path: str, conn: sqlite3.Connection, images_dir: str):
    new_watches = 0
    new_events = 0
    skipped_events = 0
    images_downloaded = 0
    total = 0

    with open(input_path, 'r') as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            total += 1
            try:
                e = json.loads(line)
            except json.JSONDecodeError:
                continue

            item_name = e.get('itemName', '')
            event_id = e.get('id', '')
            if not item_name or not event_id:
                continue

            rarity = e.get('rarity', '')
            box_name = e.get('boxName', '')
            box_tier = extract_tier(box_name)
            box_slug = e.get('boxSlug', '')
            rarity_color = e.get('rarityColor', '')
            image_url = e.get('itemImageUrl', '')
            item_value = e.get('itemValue', 0)
            acquired_at = e.get('acquiredAt', '')
            collected_at = e.get('collectedAt', '')

            # Ensure box and rarity exist
            ensure_box(conn, box_tier, box_name, box_slug)
            ensure_rarity(conn, rarity)

            # ── Watches table (flat catalog, one row per unique watch) ──
            watch_exists = conn.execute(
                'SELECT 1 FROM watches WHERE item_name = ?', (item_name,)
            ).fetchone()

            image_path = ''
            if image_url:
                ext = get_image_ext(image_url)
                bucket = price_bucket(item_value)
                image_path = os.path.join(bucket, slugify(item_name) + ext)

            if not watch_exists:
                conn.execute("""
                    INSERT INTO watches
                    (item_name, item_value, rarity_color, image_url, image_path)
                    VALUES (?, ?, ?, ?, ?)
                """, (item_name, item_value, rarity_color, image_url, image_path))
                new_watches += 1

                if image_url and image_path:
                    full_path = os.path.join(images_dir, image_path)
                    if download_image(image_url, full_path):
                        images_downloaded += 1
                    time.sleep(0.1)

            # ── Events table ──
            try:
                conn.execute("""
                    INSERT OR IGNORE INTO events
                    (id, username, platform, box_name, box_tier, box_slug,
                     item_name, item_value, rarity, rarity_color, item_image_url,
                     acquired_at, collected_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    event_id, e.get('username', ''), e.get('platform', ''),
                    box_name, box_tier, box_slug,
                    item_name, item_value, rarity, rarity_color, image_url,
                    acquired_at, collected_at,
                ))
                new_events += 1
            except sqlite3.IntegrityError:
                skipped_events += 1

    conn.commit()

    watch_total = conn.execute('SELECT COUNT(*) FROM watches').fetchone()[0]
    event_total = conn.execute('SELECT COUNT(*) FROM events').fetchone()[0]

    print(f'\nProcessed {total} lines from {input_path}')
    print(f'  Events:  {new_events} new, {skipped_events} skipped (dupes)')
    print(f'  Watches: {new_watches} new')
    print(f'  Images:  {images_downloaded} downloaded')
    print(f'  Totals:  {event_total} events, {watch_total} unique watches in DB')


def main():
    parser = argparse.ArgumentParser(description='Build unified IcyBox database')
    parser.add_argument('--input', default='./icybox-data.jsonl',
                        help='Path to JSONL data file (default: ./icybox-data.jsonl)')
    parser.add_argument('--output', default='./watch-catalog',
                        help='Output directory (default: ./watch-catalog)')
    args = parser.parse_args()

    if not os.path.exists(args.input):
        print(f'Error: Input file not found: {args.input}')
        sys.exit(1)

    output_dir = Path(args.output)
    images_dir = output_dir / 'images'
    db_path = output_dir / 'icybox.db'
    os.makedirs(images_dir, exist_ok=True)

    print(f'Input:  {args.input}')
    print(f'Output: {output_dir}')
    print(f'DB:     {db_path}')

    conn = init_db(str(db_path))
    process(args.input, conn, str(images_dir))
    conn.close()

    print(f'\nDone. Open {db_path} with DB Browser for SQLite.')


if __name__ == '__main__':
    main()
