#!/usr/bin/env python3
"""
Scrape IcyBox box pages for stated odds, value ranges, and grail watch listings.

Discovers boxes from the database (populated by build_db.py from events).
No hardcoded box list — new boxes in the stream get scraped automatically.

Requires: pip3 install playwright && python3 -m playwright install chromium

Usage:
  python3 tools/scrape_boxes.py
  python3 tools/scrape_boxes.py --output ./watch-catalog
  python3 tools/scrape_boxes.py --output '/Volumes/Crucial X9/projects/icybox_stream'
"""

import argparse
import os
import re
import sqlite3
import sys
import time
import urllib.request
import urllib.error
from datetime import datetime, timezone
from pathlib import Path

try:
    from playwright.sync_api import sync_playwright
except ImportError:
    print('Error: playwright is required.')
    print('Install it with:')
    print('  pip3 install playwright')
    print('  python3 -m playwright install chromium')
    sys.exit(1)


BASE_URL = 'https://www.icybox.io/box/'

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) '
                  'AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4 Safari/605.1.15'
}


def slugify(text: str) -> str:
    text = text.lower().strip()
    text = re.sub(r'[^\w\s-]', '', text)
    text = re.sub(r'[\s_]+', '-', text)
    text = re.sub(r'-+', '-', text)
    return text.strip('-')


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


def download_image(url: str, dest: str) -> bool:
    if not url or os.path.exists(dest):
        return os.path.exists(dest)
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    try:
        req = urllib.request.Request(url, headers=HEADERS)
        with urllib.request.urlopen(req, timeout=15) as resp:
            with open(dest, 'wb') as f:
                f.write(resp.read())
        return True
    except (urllib.error.URLError, OSError, TimeoutError) as e:
        print(f'  [warn] Failed to download {url}: {e}')
        return False


def parse_page_content(text: str):
    """Parse box price, odds, and grails from the rendered page text."""
    odds = []
    grails = []
    box_cost = None

    # Parse box price: "$500.00USDC" or "$50.00 USDC"
    cost_match = re.search(r'\$([0-9,]+(?:\.\d+)?)\s*USDC', text)
    if cost_match:
        box_cost = float(cost_match.group(1).replace(',', ''))

    # Parse odds: "Rarity: $min - $max RarityXX%"
    odds_pattern = r'(\w[\w\s]*?):\s*\$([0-9,]+)\s*-\s*\$([0-9,]+)\s+\1\s*([\d.]+)%'
    for match in re.finditer(odds_pattern, text):
        rarity = match.group(1).strip()
        min_val = float(match.group(2).replace(',', ''))
        max_val = float(match.group(3).replace(',', ''))
        pct = float(match.group(4))
        odds.append({
            'rarity': rarity,
            'rarity_key': rarity.lower().replace(' ', '_'),
            'odds_pct': pct,
            'min_value': min_val,
            'max_value': max_val,
        })

    # Parse grails: ![Name](url)\n\nName\n\n$XX,XXX
    grail_pattern = r'!\[([^\]]+)\]\((https://[^\)]+)\)\s*\n\s*\n\s*\1\s*\n\s*\n\s*\$([0-9,]+)'
    grail_section = text
    marker = 'Top watches in this box'
    idx = text.find(marker)
    if idx >= 0:
        grail_section = text[idx:]

    for match in re.finditer(grail_pattern, grail_section):
        name = match.group(1).strip()
        image_url = match.group(2).strip()
        value = float(match.group(3).replace(',', ''))
        grails.append({
            'item_name': name,
            'item_value': value,
            'image_url': image_url,
        })

    return odds, grails, box_cost


def init_tables(conn: sqlite3.Connection):
    """Create scraper-specific tables (box_pricing, stated_odds, listed_watches)."""
    # Migrate old stated_odds if needed
    old_schema = conn.execute("PRAGMA table_info(stated_odds)").fetchall()
    old_cols = [row[1] for row in old_schema] if old_schema else []
    if old_cols and 'effective_from' not in old_cols:
        conn.execute("DROP TABLE IF EXISTS stated_odds")

    conn.execute("""
        CREATE TABLE IF NOT EXISTS box_pricing (
            box_tier TEXT NOT NULL,
            cost REAL NOT NULL,
            effective_from TEXT NOT NULL,
            effective_until TEXT,
            PRIMARY KEY (box_tier, effective_from)
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS stated_odds (
            box_tier TEXT NOT NULL,
            rarity_key TEXT NOT NULL,
            rarity_label TEXT NOT NULL,
            odds_pct REAL NOT NULL,
            min_value REAL,
            max_value REAL,
            effective_from TEXT NOT NULL,
            effective_until TEXT,
            PRIMARY KEY (box_tier, rarity_key, effective_from)
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS listed_watches (
            item_name TEXT NOT NULL,
            box_tier TEXT NOT NULL,
            item_value REAL NOT NULL,
            image_url TEXT DEFAULT '',
            image_path TEXT DEFAULT '',
            listed INTEGER DEFAULT 1,
            first_scraped_at TEXT NOT NULL,
            last_scraped_at TEXT NOT NULL,
            delisted_at TEXT,
            PRIMARY KEY (item_name, box_tier)
        )
    """)

    conn.commit()


def get_boxes_to_scrape(conn: sqlite3.Connection) -> list:
    """Get all non-deprecated boxes from the database."""
    rows = conn.execute("""
        SELECT box_tier, box_slug FROM boxes
        WHERE deprecated_at IS NULL AND box_slug != ''
    """).fetchall()
    return [{'tier': row[0], 'slug': row[1]} for row in rows]


def process_box(conn: sqlite3.Connection, page, box: dict, images_dir: str, now: str) -> bool:
    """Scrape a single box page. Returns False if the page is gone (404)."""
    slug = box['slug']
    tier = box['tier']
    url = BASE_URL + slug

    print(f'\nScraping {tier} Box: {url}')

    response = page.goto(url, wait_until='domcontentloaded', timeout=60000)

    # Check if page exists
    if response and response.status == 404:
        print(f'  ⚠ Page not found (404) — marking {tier} as deprecated')
        conn.execute("UPDATE boxes SET deprecated_at = ? WHERE box_tier = ?", (now, tier))
        conn.commit()
        return False

    try:
        page.wait_for_selector('text=Odds & Values', timeout=15000)
    except:
        pass
    time.sleep(3)

    import html
    text = html.unescape(page.inner_text('body'))

    odds, _, box_cost = parse_page_content(text)

    if not odds:
        raw = page.content()
        odds, _, raw_cost = parse_page_content(raw)
        if box_cost is None:
            box_cost = raw_cost

    # Extract grails using DOM selectors — more reliable than regex on rendered text
    grails = []
    try:
        # Wait for grails section
        page.wait_for_selector('text=Top watches in this box', timeout=5000)
        # Find all grail items: each has an img with alt text and a sibling with the price
        grail_container = page.query_selector('text=Top watches in this box')
        if grail_container:
            # Get the parent section and find all image+price pairs after it
            items = page.evaluate("""() => {
                const results = [];
                const header = [...document.querySelectorAll('*')].find(
                    el => el.textContent.trim() === 'Top watches in this box'
                );
                if (!header) return results;
                const container = header.closest('div')?.parentElement || header.parentElement;
                if (!container) return results;
                const imgs = container.querySelectorAll('img[alt][src*="cloudfront"]');
                imgs.forEach(img => {
                    const alt = img.getAttribute('alt');
                    const src = img.getAttribute('src');
                    // Find the price near this image
                    const parent = img.closest('div')?.parentElement;
                    if (!parent) return;
                    const text = parent.textContent || '';
                    const priceMatch = text.match(/\\$(\\d[\\d,]*)/);
                    if (priceMatch && alt && src) {
                        results.push({
                            item_name: alt.trim(),
                            item_value: parseFloat(priceMatch[1].replace(/,/g, '')),
                            image_url: src.trim()
                        });
                    }
                });
                return results;
            }""")
            if items:
                # Deduplicate
                seen = set()
                for item in items:
                    if item['item_name'] not in seen and item['item_value'] >= 100:
                        seen.add(item['item_name'])
                        grails.append(item)
    except:
        pass

    # ── Update box price ──
    if box_cost is not None:
        # Update current price on boxes table
        current_price = conn.execute(
            'SELECT price FROM boxes WHERE box_tier = ?', (tier,)
        ).fetchone()
        if current_price and current_price[0] is not None and current_price[0] != box_cost:
            print(f'  ⚠ Box price changed: ${current_price[0]} → ${box_cost}')
        conn.execute("UPDATE boxes SET price = ? WHERE box_tier = ?", (box_cost, tier))

        # Version in box_pricing
        active_price = conn.execute("""
            SELECT cost FROM box_pricing
            WHERE box_tier = ? AND effective_until IS NULL
        """, (tier,)).fetchone()

        if active_price is None:
            conn.execute("""
                INSERT INTO box_pricing (box_tier, cost, effective_from, effective_until)
                VALUES (?, ?, ?, NULL)
            """, (tier, box_cost, now))
        elif active_price[0] != box_cost:
            conn.execute("""
                UPDATE box_pricing SET effective_until = ?
                WHERE box_tier = ? AND effective_until IS NULL
            """, (now, tier))
            conn.execute("""
                INSERT INTO box_pricing (box_tier, cost, effective_from, effective_until)
                VALUES (?, ?, ?, NULL)
            """, (tier, box_cost, now))

        print(f'  Box cost: ${box_cost:.2f}')

    # ── Update stated odds ──
    if odds:
        print(f'  Found {len(odds)} rarity tiers:')
        for o in odds:
            print(f'    {o["rarity"]}: {o["odds_pct"]}% (${o["min_value"]:.0f} - ${o["max_value"]:.0f})')

            # Ensure rarity exists
            existing_rarity = conn.execute(
                "SELECT 1 FROM rarities WHERE rarity_key = ?", (o['rarity_key'],)
            ).fetchone()
            if not existing_rarity:
                full_name = o['rarity']
                short_name = full_name.split()[-1] if ' ' in full_name else full_name
                conn.execute(
                    "INSERT INTO rarities (rarity_key, full_name, short_name) VALUES (?, ?, ?)",
                    (o['rarity_key'], full_name, short_name)
                )

            current = conn.execute("""
                SELECT odds_pct, min_value, max_value FROM stated_odds
                WHERE box_tier = ? AND rarity_key = ? AND effective_until IS NULL
            """, (tier, o['rarity_key'])).fetchone()

            if current is None:
                conn.execute("""
                    INSERT INTO stated_odds
                    (box_tier, rarity_key, rarity_label, odds_pct, min_value, max_value, effective_from, effective_until)
                    VALUES (?, ?, ?, ?, ?, ?, ?, NULL)
                """, (tier, o['rarity_key'], o['rarity'], o['odds_pct'], o['min_value'], o['max_value'], now))
            elif current[0] != o['odds_pct'] or current[1] != o['min_value'] or current[2] != o['max_value']:
                print(f'      ⚠ CHANGED from {current[0]}% to {o["odds_pct"]}%')
                conn.execute("""
                    UPDATE stated_odds SET effective_until = ?
                    WHERE box_tier = ? AND rarity_key = ? AND effective_until IS NULL
                """, (now, tier, o['rarity_key']))
                conn.execute("""
                    INSERT INTO stated_odds
                    (box_tier, rarity_key, rarity_label, odds_pct, min_value, max_value, effective_from, effective_until)
                    VALUES (?, ?, ?, ?, ?, ?, ?, NULL)
                """, (tier, o['rarity_key'], o['rarity'], o['odds_pct'], o['min_value'], o['max_value'], now))
    else:
        print('  [warn] No odds found on page')

    # ── Update listed watches (grails) ──
    images_downloaded = 0
    if grails:
        print(f'  Found {len(grails)} grail watches:')

        conn.execute(
            "UPDATE listed_watches SET listed = 0, delisted_at = ? WHERE box_tier = ? AND listed = 1",
            (now, tier)
        )

        for g in grails:
            bucket = price_bucket(g['item_value'])
            image_path = os.path.join(bucket, slugify(g['item_name']) + '.png')

            existing = conn.execute(
                'SELECT 1 FROM listed_watches WHERE item_name = ? AND box_tier = ?',
                (g['item_name'], tier)
            ).fetchone()

            if existing:
                conn.execute("""
                    UPDATE listed_watches
                    SET item_value = ?, image_url = ?, image_path = ?, listed = 1, last_scraped_at = ?, delisted_at = NULL
                    WHERE item_name = ? AND box_tier = ?
                """, (g['item_value'], g['image_url'], image_path, now, g['item_name'], tier))
            else:
                conn.execute("""
                    INSERT INTO listed_watches
                    (item_name, box_tier, item_value, image_url, image_path, listed, first_scraped_at, last_scraped_at, delisted_at)
                    VALUES (?, ?, ?, ?, ?, 1, ?, ?, NULL)
                """, (g['item_name'], tier, g['item_value'], g['image_url'], image_path, now, now))

            full_path = os.path.join(images_dir, image_path)
            if download_image(g['image_url'], full_path):
                images_downloaded += 1
            time.sleep(0.1)

            print(f'    ${g["item_value"]:>10,.0f}  {g["item_name"]}')

        delisted = conn.execute(
            'SELECT COUNT(*) FROM listed_watches WHERE box_tier = ? AND listed = 0', (tier,)
        ).fetchone()[0]
        if delisted > 0:
            print(f'  {delisted} watches no longer listed (marked as delisted)')
        print(f'  {images_downloaded} images downloaded')
    else:
        print('  [warn] No grail watches found on page')

    conn.commit()
    return True


def main():
    parser = argparse.ArgumentParser(description='Scrape IcyBox box pages')
    parser.add_argument('--output', default='./watch-catalog',
                        help='Output directory with icybox.db (default: ./watch-catalog)')
    args = parser.parse_args()

    output_dir = Path(args.output)
    images_dir = output_dir / 'images'
    db_path = output_dir / 'icybox.db'

    if not db_path.exists():
        print(f'Error: Database not found at {db_path}')
        print('Run build_db.py first to create the database.')
        sys.exit(1)

    os.makedirs(images_dir, exist_ok=True)
    now = datetime.now(timezone.utc).isoformat()

    conn = sqlite3.connect(str(db_path))
    init_tables(conn)

    # Get boxes to scrape from the database
    boxes = get_boxes_to_scrape(conn)

    if not boxes:
        print('No boxes found in database. Run build_db.py first to ingest events.')
        conn.close()
        sys.exit(1)

    print(f'DB:     {db_path}')
    print(f'Images: {images_dir}')
    print(f'Boxes:  {len(boxes)} to scrape ({", ".join(b["tier"] for b in boxes)})')

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.route('**/activity/stream**', lambda route: route.abort())

        for box in boxes:
            process_box(conn, page, box, str(images_dir), now)
            time.sleep(1)

        browser.close()

    total_odds = conn.execute('SELECT COUNT(*) FROM stated_odds WHERE effective_until IS NULL').fetchone()[0]
    historical_odds = conn.execute('SELECT COUNT(*) FROM stated_odds WHERE effective_until IS NOT NULL').fetchone()[0]
    total_listed = conn.execute('SELECT COUNT(*) FROM listed_watches WHERE listed = 1').fetchone()[0]
    total_delisted = conn.execute('SELECT COUNT(*) FROM listed_watches WHERE listed = 0').fetchone()[0]
    deprecated_boxes = conn.execute('SELECT COUNT(*) FROM boxes WHERE deprecated_at IS NOT NULL').fetchone()[0]

    print(f'\nDone.')
    print(f'  {total_odds} current rarity tiers with stated odds')
    if historical_odds > 0:
        print(f'  {historical_odds} historical odds records (changed)')
    print(f'  {total_listed} watches currently listed')
    if total_delisted > 0:
        print(f'  {total_delisted} watches previously listed (now delisted)')
    if deprecated_boxes > 0:
        print(f'  {deprecated_boxes} boxes deprecated (page gone)')

    conn.close()


if __name__ == '__main__':
    main()
