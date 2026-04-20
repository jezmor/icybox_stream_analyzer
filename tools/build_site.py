#!/usr/bin/env python3
"""
Generate a static HTML watch catalog from icybox.db.

Reads watches, events, and listed_watches from the database and generates
a browsable static site with watch cards, photos, values, and rarity badges.

Usage:
  python tools/build_site.py --db '/Volumes/Crucial X9/projects/icybox_stream/icybox.db' --images '/Volumes/Crucial X9/projects/icybox_stream/images'
  python tools/build_site.py --db ./watch-catalog/icybox.db --images ./watch-catalog/images
"""

import argparse
import html
import os
import sqlite3
import sys
from pathlib import Path
from urllib.parse import quote


def query_watches(conn: sqlite3.Connection) -> list:
    """Get all watches with their rarity per box tier and drop counts."""
    rows = conn.execute("""
        SELECT
            item_name,
            item_value,
            MAX(CASE WHEN box_tier = 'Bronze' THEN rarity END) AS bronze,
            MAX(CASE WHEN box_tier = 'Silver' THEN rarity END) AS silver,
            MAX(CASE WHEN box_tier = 'Gold' THEN rarity END) AS gold,
            MAX(CASE WHEN box_tier = 'Icy' THEN rarity END) AS icy,
            SUM(CASE WHEN box_tier = 'Bronze' THEN 1 ELSE 0 END) AS bronze_count,
            SUM(CASE WHEN box_tier = 'Silver' THEN 1 ELSE 0 END) AS silver_count,
            SUM(CASE WHEN box_tier = 'Gold' THEN 1 ELSE 0 END) AS gold_count,
            SUM(CASE WHEN box_tier = 'Icy' THEN 1 ELSE 0 END) AS icy_count,
            COUNT(*) AS total_drops
        FROM events
        GROUP BY item_name
    """).fetchall()

    watches = []
    for r in rows:
        watches.append({
            'name': r[0], 'value': r[1],
            'bronze': r[2], 'silver': r[3], 'gold': r[4], 'icy': r[5],
            'bronze_count': r[6], 'silver_count': r[7], 'gold_count': r[8], 'icy_count': r[9],
            'total_drops': r[10], 'source': 'stream',
        })

    # Add grail watches not seen in stream
    listed = conn.execute("""
        SELECT lw.item_name, lw.item_value, lw.box_tier
        FROM listed_watches lw
        WHERE lw.listed = 1
          AND lw.item_name NOT IN (SELECT DISTINCT item_name FROM events)
    """).fetchall()

    grail_map = {}
    for r in listed:
        name, value, tier = r
        if name not in grail_map:
            grail_map[name] = {'name': name, 'value': value, 'bronze': None, 'silver': None,
                               'gold': None, 'icy': None, 'bronze_count': 0, 'silver_count': 0,
                               'gold_count': 0, 'icy_count': 0, 'total_drops': 0, 'source': 'listed'}
        grail_map[name][tier.lower()] = 'grail'

    watches.extend(grail_map.values())
    watches.sort(key=lambda w: w['value'], reverse=True)
    return watches


def query_watch_images(conn: sqlite3.Connection) -> dict:
    """Get image paths for watches."""
    images = {}
    for row in conn.execute("SELECT item_name, image_path FROM watches WHERE image_path != ''"):
        images[row[0]] = row[1]
    for row in conn.execute("SELECT item_name, image_path FROM listed_watches WHERE image_path != ''"):
        if row[0] not in images:
            images[row[0]] = row[1]
    return images


def query_stats(conn: sqlite3.Connection) -> dict:
    """Get summary stats."""
    total_events = conn.execute("SELECT COUNT(*) FROM events").fetchone()[0]
    total_watches = conn.execute("SELECT COUNT(DISTINCT item_name) FROM events").fetchone()[0]
    total_users = conn.execute("SELECT COUNT(DISTINCT username) FROM events").fetchone()[0]
    return {'events': total_events, 'watches': total_watches, 'users': total_users}


RARITY_COLORS = {
    'quartz': '#9ca3af',
    'automatic': '#22c55e',
    'chronograph': '#3b82f6',
    'tourbillon': '#a855f7',
    'grand_tourbillon': '#ef4444',
    'grail': '#eab308',
}


def rarity_badge(rarity: str, tier: str, count: int) -> str:
    if not rarity:
        return ''
    color = RARITY_COLORS.get(rarity, '#6b7280')
    label = rarity.replace('_', ' ').title()
    count_str = f' ({count})' if count > 0 else ''
    return f'<span class="badge" style="background:{color}" title="{tier}: {label}{count_str}">{tier[0]}</span>'


def esc(text: str) -> str:
    return html.escape(str(text))


def build_html(watches: list, images: dict, stats: dict, images_dir: str) -> str:
    cards = []
    all_rarities = set()

    for w in watches:
        img_path = images.get(w['name'], '')
        img_src = 'file://' + quote(os.path.join(images_dir, img_path))
        img_tag = f'<img src="{img_src}" alt="{esc(w["name"])}" loading="lazy">' if img_path else '<div class="no-image">No Image</div>'

        badges = ''
        rarities_for_watch = []
        for tier, key, count_key in [('Bronze', 'bronze', 'bronze_count'), ('Silver', 'silver', 'silver_count'),
                                      ('Gold', 'gold', 'gold_count'), ('Icy', 'icy', 'icy_count')]:
            r = w.get(key)
            if r:
                badges += rarity_badge(r, tier, w.get(count_key, 0))
                rarities_for_watch.append(r)
                all_rarities.add(r)

        rarity_classes = ' '.join(f'rarity-{r}' for r in set(rarities_for_watch))
        tier_classes = ''
        if w['bronze']: tier_classes += ' tier-bronze'
        if w['silver']: tier_classes += ' tier-silver'
        if w['gold']: tier_classes += ' tier-gold'
        if w['icy']: tier_classes += ' tier-icy'

        source_badge = '<span class="source-badge listed">Listed Only</span>' if w['source'] == 'listed' else ''

        cards.append(f'''
        <div class="card{tier_classes} {rarity_classes}" data-value="{w['value']}" data-drops="{w['total_drops']}">
            <div class="card-image">{img_tag}</div>
            <div class="card-body">
                <div class="card-name">{esc(w['name'])}</div>
                <div class="card-value">${w['value']:,.2f}</div>
                <div class="card-badges">{badges}{source_badge}</div>
                <div class="card-drops">{w['total_drops']} drops</div>
            </div>
        </div>''')

    cards_html = '\n'.join(cards)

    return f'''<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>IcyBox Watch Catalog</title>
<style>
* {{ margin: 0; padding: 0; box-sizing: border-box; }}
body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; background: #0f0f0f; color: #e5e5e5; }}
.header {{ padding: 24px; text-align: center; border-bottom: 1px solid #222; }}
.header h1 {{ font-size: 24px; margin-bottom: 8px; }}
.header .stats {{ color: #888; font-size: 14px; }}
.filters {{ padding: 16px 24px; display: flex; gap: 12px; flex-wrap: wrap; align-items: center; border-bottom: 1px solid #222; }}
.filters label {{ color: #888; font-size: 13px; }}
.filters select, .filters input {{ background: #1a1a1a; color: #e5e5e5; border: 1px solid #333; border-radius: 6px; padding: 6px 10px; font-size: 13px; }}
.grid {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(220px, 1fr)); gap: 16px; padding: 24px; }}
.card {{ background: #1a1a1a; border-radius: 12px; overflow: hidden; border: 1px solid #222; transition: border-color 0.2s; }}
.card:hover {{ border-color: #444; }}
.card-image {{ aspect-ratio: 1; display: flex; align-items: center; justify-content: center; background: #111; padding: 16px; }}
.card-image img {{ max-width: 100%; max-height: 100%; object-fit: contain; }}
.no-image {{ color: #444; font-size: 13px; }}
.card-body {{ padding: 12px; }}
.card-name {{ font-size: 13px; font-weight: 600; margin-bottom: 4px; line-height: 1.3; }}
.card-value {{ font-size: 18px; font-weight: 700; color: #22c55e; margin-bottom: 8px; }}
.card-badges {{ display: flex; gap: 4px; flex-wrap: wrap; margin-bottom: 4px; }}
.badge {{ display: inline-block; padding: 2px 8px; border-radius: 4px; font-size: 11px; font-weight: 700; color: #fff; }}
.source-badge {{ font-size: 10px; padding: 2px 6px; border-radius: 3px; }}
.source-badge.listed {{ background: #854d0e; color: #fbbf24; }}
.card-drops {{ font-size: 11px; color: #666; }}
.hidden {{ display: none; }}
</style>
</head>
<body>
<div class="header">
    <h1>IcyBox Watch Catalog</h1>
    <div class="stats">{stats['watches']} watches &middot; {stats['events']:,} events &middot; {stats['users']:,} users</div>
</div>
<div class="filters">
    <label>Box:</label>
    <select id="filterTier">
        <option value="">All</option>
        <option value="tier-bronze">Bronze</option>
        <option value="tier-silver">Silver</option>
        <option value="tier-gold">Gold</option>
        <option value="tier-icy">Icy</option>
    </select>
    <label>Rarity:</label>
    <select id="filterRarity">
        <option value="">All</option>
        <option value="rarity-quartz">Quartz</option>
        <option value="rarity-automatic">Automatic</option>
        <option value="rarity-chronograph">Chronograph</option>
        <option value="rarity-tourbillon">Tourbillon</option>
        <option value="rarity-grand_tourbillon">Grand Tourbillon</option>
        <option value="rarity-grail">Grail</option>
    </select>
    <label>Search:</label>
    <input type="text" id="filterSearch" placeholder="Watch name...">
    <label>Sort:</label>
    <select id="sortBy">
        <option value="value-desc">Value (high → low)</option>
        <option value="value-asc">Value (low → high)</option>
        <option value="drops-desc">Drops (most)</option>
        <option value="drops-asc">Drops (least)</option>
    </select>
</div>
<div class="grid" id="grid">
{cards_html}
</div>
<script>
const grid = document.getElementById('grid');
const cards = [...grid.querySelectorAll('.card')];
const filterTier = document.getElementById('filterTier');
const filterRarity = document.getElementById('filterRarity');
const filterSearch = document.getElementById('filterSearch');
const sortBy = document.getElementById('sortBy');

function applyFilters() {{
    const tier = filterTier.value;
    const rarity = filterRarity.value;
    const search = filterSearch.value.toLowerCase();
    const sort = sortBy.value;

    cards.forEach(card => {{
        const matchTier = !tier || card.classList.contains(tier);
        const matchRarity = !rarity || card.classList.contains(rarity);
        const matchSearch = !search || card.querySelector('.card-name').textContent.toLowerCase().includes(search);
        card.classList.toggle('hidden', !(matchTier && matchRarity && matchSearch));
    }});

    const visible = cards.filter(c => !c.classList.contains('hidden'));
    visible.sort((a, b) => {{
        const av = parseFloat(a.dataset.value);
        const bv = parseFloat(b.dataset.value);
        const ad = parseInt(a.dataset.drops);
        const bd = parseInt(b.dataset.drops);
        if (sort === 'value-desc') return bv - av;
        if (sort === 'value-asc') return av - bv;
        if (sort === 'drops-desc') return bd - ad;
        if (sort === 'drops-asc') return ad - bd;
        return 0;
    }});
    visible.forEach(card => grid.appendChild(card));
    cards.filter(c => c.classList.contains('hidden')).forEach(c => grid.appendChild(c));
}}

filterTier.addEventListener('change', applyFilters);
filterRarity.addEventListener('change', applyFilters);
filterSearch.addEventListener('input', applyFilters);
sortBy.addEventListener('change', applyFilters);
</script>
</body>
</html>'''


def main():
    parser = argparse.ArgumentParser(description='Generate static watch catalog site')
    parser.add_argument('--db', required=True, help='Path to icybox.db')
    parser.add_argument('--images', required=True, help='Path to images directory')
    parser.add_argument('--output', default='./web/site', help='Output directory (default: ./web/site)')
    args = parser.parse_args()

    if not os.path.exists(args.db):
        print(f'Error: Database not found: {args.db}')
        sys.exit(1)

    output_dir = Path(args.output)
    os.makedirs(output_dir, exist_ok=True)

    conn = sqlite3.connect(args.db)
    watches = query_watches(conn)
    images = query_watch_images(conn)
    stats = query_stats(conn)
    conn.close()

    print(f'Found {len(watches)} watches')

    # Generate HTML
    html_content = build_html(watches, images, stats, os.path.abspath(args.images))
    (output_dir / 'index.html').write_text(html_content)

    print(f'Site generated at {output_dir}/index.html')
    print(f'Open in browser: file://{os.path.abspath(output_dir)}/index.html')


if __name__ == '__main__':
    main()
