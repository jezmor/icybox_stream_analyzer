"""Tests for database query functions in dashboard/app.py."""

import sqlite3
import pytest
import os
import sys

# Add project root to path so we can import the dashboard module
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dashboard.app import (
    app,
    slugify,
    query_watches,
    query_watch_detail,
    query_box_page,
    query_stats,
    get_available_tiers,
)


@pytest.fixture
def test_db(tmp_path):
    """Create a test database with sample data."""
    db_path = str(tmp_path / "test.db")
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row

    # Create tables
    conn.execute("""
        CREATE TABLE boxes (
            box_tier TEXT PRIMARY KEY,
            box_name TEXT NOT NULL,
            box_slug TEXT DEFAULT '',
            price REAL,
            deprecated_at TEXT,
            first_seen_at TEXT
        )
    """)
    conn.execute("""
        CREATE TABLE watches (
            item_name TEXT PRIMARY KEY,
            item_value REAL NOT NULL,
            rarity_color TEXT DEFAULT '',
            image_url TEXT DEFAULT '',
            image_path TEXT DEFAULT ''
        )
    """)
    conn.execute("""
        CREATE TABLE events (
            id TEXT PRIMARY KEY,
            username TEXT NOT NULL,
            platform TEXT DEFAULT '',
            box_name TEXT NOT NULL,
            box_tier TEXT NOT NULL,
            box_slug TEXT DEFAULT '',
            item_name TEXT NOT NULL,
            item_value REAL NOT NULL,
            rarity TEXT NOT NULL,
            rarity_color TEXT DEFAULT '',
            item_image_url TEXT DEFAULT '',
            acquired_at TEXT NOT NULL,
            collected_at TEXT NOT NULL
        )
    """)
    conn.execute("""
        CREATE TABLE listed_watches (
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
    conn.execute("""
        CREATE TABLE box_pricing (
            box_tier TEXT NOT NULL,
            cost REAL NOT NULL,
            effective_from TEXT NOT NULL,
            effective_until TEXT,
            PRIMARY KEY (box_tier, effective_from)
        )
    """)
    conn.execute("""
        CREATE TABLE stated_odds (
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
        CREATE TABLE user_watch_data (
            item_name TEXT PRIMARY KEY,
            msrp REAL,
            market_value REAL,
            notes TEXT,
            reference_number TEXT,
            market_value_source TEXT,
            manufacturer_url TEXT
        )
    """)

    # Insert sample boxes
    conn.executemany("INSERT INTO boxes VALUES (?, ?, ?, ?, ?, ?)", [
        ("Bronze", "Bronze Box", "bronze-box", 50.0, None, "2024-01-01"),
        ("Silver", "Silver Box", "silver-box", 100.0, None, "2024-01-01"),
        ("Gold", "Gold Box", "gold-box", 500.0, None, "2024-01-01"),
        ("Icy", "Icy Box", "icy-box", 1000.0, None, "2024-01-01"),
        ("Legacy", "Legacy Box", "legacy-box", 25.0, "2024-06-01", "2024-01-01"),
    ])

    # Insert sample watches
    conn.executemany("INSERT INTO watches VALUES (?, ?, ?, ?, ?)", [
        ("Casio G-Shock", 150.0, "#9ca3af", "http://img/casio.png", "$100-$1000/casio-g-shock.png"),
        ("Seiko Presage", 450.0, "#22c55e", "http://img/seiko.png", "$100-$1000/seiko-presage.png"),
        ("Omega Seamaster", 5000.0, "#3b82f6", "http://img/omega.png", "$1000-$10000/omega-seamaster.png"),
        ("Rolex Submariner", 12000.0, "#a855f7", "http://img/rolex.png", "$10000-$100000/rolex-submariner.png"),
    ])

    # Insert sample events
    events = [
        ("e1", "user1", "twitch", "Bronze Box", "Bronze", "bronze-box", "Casio G-Shock", 150.0, "quartz", "#9ca3af", "", "2024-01-10T00:00:00Z", "2024-01-10T00:00:00Z"),
        ("e2", "user2", "twitch", "Bronze Box", "Bronze", "bronze-box", "Casio G-Shock", 150.0, "quartz", "#9ca3af", "", "2024-01-11T00:00:00Z", "2024-01-11T00:00:00Z"),
        ("e3", "user1", "twitch", "Bronze Box", "Bronze", "bronze-box", "Seiko Presage", 450.0, "automatic", "#22c55e", "", "2024-01-12T00:00:00Z", "2024-01-12T00:00:00Z"),
        ("e4", "user3", "twitch", "Silver Box", "Silver", "silver-box", "Seiko Presage", 450.0, "quartz", "#9ca3af", "", "2024-02-01T00:00:00Z", "2024-02-01T00:00:00Z"),
        ("e5", "user1", "twitch", "Gold Box", "Gold", "gold-box", "Omega Seamaster", 5000.0, "chronograph", "#3b82f6", "", "2024-02-15T00:00:00Z", "2024-02-15T00:00:00Z"),
        ("e6", "user2", "twitch", "Gold Box", "Gold", "gold-box", "Omega Seamaster", 5000.0, "chronograph", "#3b82f6", "", "2024-02-16T00:00:00Z", "2024-02-16T00:00:00Z"),
        ("e7", "user2", "twitch", "Gold Box", "Gold", "gold-box", "Omega Seamaster", 5000.0, "chronograph", "#3b82f6", "", "2024-02-17T00:00:00Z", "2024-02-17T00:00:00Z"),
        ("e8", "user3", "twitch", "Icy Box", "Icy", "icy-box", "Rolex Submariner", 12000.0, "tourbillon", "#a855f7", "", "2024-03-01T00:00:00Z", "2024-03-01T00:00:00Z"),
    ]
    conn.executemany("INSERT INTO events VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", events)

    # Insert listed-only watch (grail, never dropped)
    conn.execute("""
        INSERT INTO listed_watches VALUES
        ('Patek Philippe Nautilus', 'Gold', 150000.0, 'http://img/patek.png',
         '$100000+/patek-philippe-nautilus.png', 1, '2024-01-01', '2024-03-01', NULL)
    """)

    # Insert box pricing
    conn.execute("INSERT INTO box_pricing VALUES ('Gold', 500.0, '2024-01-01', NULL)")
    conn.execute("INSERT INTO box_pricing VALUES ('Bronze', 50.0, '2024-01-01', NULL)")

    # Insert stated odds
    conn.executemany("""
        INSERT INTO stated_odds VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, [
        ("Gold", "chronograph", "Chronograph", 60.0, 1000.0, 10000.0, "2024-01-01", None),
        ("Gold", "tourbillon", "Tourbillon", 30.0, 5000.0, 50000.0, "2024-01-01", None),
        ("Gold", "grand_tourbillon", "Grand Tourbillon", 10.0, 10000.0, 100000.0, "2024-01-01", None),
    ])

    # Insert user data for one watch
    conn.execute("INSERT INTO user_watch_data VALUES ('Omega Seamaster', 4800.0, 5200.0, 'Great daily driver', NULL, NULL, NULL)")

    conn.commit()

    # Configure the Flask app to use this test DB
    app.config["DB_PATH"] = db_path

    yield conn
    conn.close()


# ── query_watches tests ──

class TestQueryWatches:
    def test_returns_all_stream_watches(self, test_db):
        result = query_watches(test_db)
        stream_watches = [w for w in result if w["source"] == "stream"]
        names = {w["name"] for w in stream_watches}
        assert names == {"Casio G-Shock", "Seiko Presage", "Omega Seamaster", "Rolex Submariner"}

    def test_includes_listed_only_watches(self, test_db):
        result = query_watches(test_db)
        listed = [w for w in result if w["source"] == "listed"]
        assert len(listed) == 1
        assert listed[0]["name"] == "Patek Philippe Nautilus"
        assert listed[0]["gold"] == "grail"

    def test_slug_generation(self, test_db):
        result = query_watches(test_db)
        casio = next(w for w in result if w["name"] == "Casio G-Shock")
        assert casio["slug"] == "casio-g-shock"

    def test_image_path_from_watches_table(self, test_db):
        result = query_watches(test_db)
        omega = next(w for w in result if w["name"] == "Omega Seamaster")
        assert omega["image_path"] == "$1000-$10000/omega-seamaster.png"

    def test_per_tier_rarity(self, test_db):
        result = query_watches(test_db)
        seiko = next(w for w in result if w["name"] == "Seiko Presage")
        assert seiko["bronze"] == "automatic"
        assert seiko["silver"] == "quartz"
        assert seiko["gold"] is None
        assert seiko["icy"] is None

    def test_per_tier_counts(self, test_db):
        result = query_watches(test_db)
        casio = next(w for w in result if w["name"] == "Casio G-Shock")
        assert casio["bronze_count"] == 2
        assert casio["silver_count"] == 0
        assert casio["total_drops"] == 2

    def test_filter_by_tier(self, test_db):
        result = query_watches(test_db, tier="Gold")
        names = {w["name"] for w in result}
        assert "Omega Seamaster" in names
        # Patek is listed as grail in Gold tier
        assert "Patek Philippe Nautilus" in names
        assert "Casio G-Shock" not in names

    def test_filter_by_rarity(self, test_db):
        result = query_watches(test_db, rarity="quartz")
        names = {w["name"] for w in result}
        assert "Casio G-Shock" in names
        assert "Seiko Presage" in names  # quartz in Silver
        assert "Omega Seamaster" not in names

    def test_filter_by_search(self, test_db):
        result = query_watches(test_db, search="omega")
        assert len(result) == 1
        assert result[0]["name"] == "Omega Seamaster"

    def test_sort_value_desc(self, test_db):
        result = query_watches(test_db, sort="value-desc")
        values = [w["value"] for w in result]
        assert values == sorted(values, reverse=True)

    def test_sort_value_asc(self, test_db):
        result = query_watches(test_db, sort="value-asc")
        values = [w["value"] for w in result]
        assert values == sorted(values)

    def test_sort_drops_desc(self, test_db):
        result = query_watches(test_db, sort="drops-desc")
        drops = [w["total_drops"] for w in result]
        assert drops == sorted(drops, reverse=True)

    def test_sort_drops_asc(self, test_db):
        result = query_watches(test_db, sort="drops-asc")
        drops = [w["total_drops"] for w in result]
        assert drops == sorted(drops)

    def test_user_data_included(self, test_db):
        result = query_watches(test_db)
        omega = next(w for w in result if w["name"] == "Omega Seamaster")
        assert omega["msrp"] == 4800.0
        assert omega["market_value"] == 5200.0

    def test_user_data_none_when_absent(self, test_db):
        result = query_watches(test_db)
        casio = next(w for w in result if w["name"] == "Casio G-Shock")
        assert casio["msrp"] is None
        assert casio["market_value"] is None

    def test_listed_only_image_path(self, test_db):
        result = query_watches(test_db)
        patek = next(w for w in result if w["name"] == "Patek Philippe Nautilus")
        assert patek["image_path"] == "$100000+/patek-philippe-nautilus.png"


# ── query_watch_detail tests ──

class TestQueryWatchDetail:
    def test_stream_watch_found(self, test_db):
        result = query_watch_detail(test_db, "omega-seamaster")
        assert result is not None
        assert result["name"] == "Omega Seamaster"
        assert result["value"] == 5000.0
        assert result["slug"] == "omega-seamaster"
        assert result["is_listed_only"] is False

    def test_per_tier_info(self, test_db):
        result = query_watch_detail(test_db, "omega-seamaster")
        assert len(result["tiers"]) == 1
        tier = result["tiers"][0]
        assert tier["tier"] == "Gold"
        assert tier["rarity"] == "chronograph"
        assert tier["drop_count"] == 3
        assert tier["tier_total_opens"] == 3
        assert tier["drop_rate"] == pytest.approx(100.0)

    def test_multi_tier_watch(self, test_db):
        result = query_watch_detail(test_db, "seiko-presage")
        assert result is not None
        tiers = {t["tier"] for t in result["tiers"]}
        assert tiers == {"Bronze", "Silver"}
        assert result["total_drops"] == 2

    def test_first_last_seen(self, test_db):
        result = query_watch_detail(test_db, "omega-seamaster")
        assert result["first_seen"] == "2024-02-15T00:00:00Z"
        assert result["last_seen"] == "2024-02-17T00:00:00Z"

    def test_listed_only_watch(self, test_db):
        result = query_watch_detail(test_db, "patek-philippe-nautilus")
        assert result is not None
        assert result["is_listed_only"] is True
        assert result["total_drops"] == 0
        assert result["first_seen"] is None
        assert result["last_seen"] is None
        assert len(result["tiers"]) == 1
        assert result["tiers"][0]["tier"] == "Gold"
        assert result["tiers"][0]["rarity"] == "grail"

    def test_not_found(self, test_db):
        result = query_watch_detail(test_db, "nonexistent-watch")
        assert result is None

    def test_user_data_included(self, test_db):
        result = query_watch_detail(test_db, "omega-seamaster")
        assert result["msrp"] == 4800.0
        assert result["market_value"] == 5200.0
        assert result["notes"] == "Great daily driver"

    def test_user_data_none_when_absent(self, test_db):
        result = query_watch_detail(test_db, "casio-g-shock")
        assert result["msrp"] is None
        assert result["market_value"] is None
        assert result["notes"] is None

    def test_image_path(self, test_db):
        result = query_watch_detail(test_db, "omega-seamaster")
        assert result["image_path"] == "$1000-$10000/omega-seamaster.png"


# ── query_box_page tests ──

class TestQueryBoxPage:
    def test_valid_tier(self, test_db):
        result = query_box_page(test_db, "Gold")
        assert result is not None
        assert result["tier"] == "Gold"
        assert result["box_name"] == "Gold Box"

    def test_box_price(self, test_db):
        result = query_box_page(test_db, "Gold")
        assert result["box_price"] == 500.0

    def test_total_opens(self, test_db):
        result = query_box_page(test_db, "Gold")
        assert result["total_opens"] == 3

    def test_stated_odds(self, test_db):
        result = query_box_page(test_db, "Gold")
        odds_keys = {o["rarity_key"] for o in result["stated_odds"]}
        assert odds_keys == {"chronograph", "tourbillon", "grand_tourbillon"}

    def test_rarity_groups(self, test_db):
        result = query_box_page(test_db, "Gold")
        assert "chronograph" in result["rarity_groups"]
        chrono_watches = result["rarity_groups"]["chronograph"]
        assert len(chrono_watches) == 1
        assert chrono_watches[0]["name"] == "Omega Seamaster"
        assert chrono_watches[0]["drop_count"] == 3
        assert chrono_watches[0]["drop_rate"] == pytest.approx(100.0)

    def test_listed_only_grails(self, test_db):
        result = query_box_page(test_db, "Gold")
        assert len(result["listed_only"]) == 1
        assert result["listed_only"][0]["name"] == "Patek Philippe Nautilus"

    def test_user_data_in_rarity_groups(self, test_db):
        result = query_box_page(test_db, "Gold")
        omega = result["rarity_groups"]["chronograph"][0]
        assert omega["msrp"] == 4800.0
        assert omega["market_value"] == 5200.0

    def test_nonexistent_tier(self, test_db):
        result = query_box_page(test_db, "Platinum")
        assert result is None

    def test_tier_with_no_pricing(self, test_db):
        result = query_box_page(test_db, "Silver")
        assert result is not None
        assert result["box_price"] is None

    def test_slug_in_watches(self, test_db):
        result = query_box_page(test_db, "Gold")
        omega = result["rarity_groups"]["chronograph"][0]
        assert omega["slug"] == "omega-seamaster"


# ── query_stats tests ──

class TestQueryStats:
    def test_counts(self, test_db):
        result = query_stats(test_db)
        assert result["watches"] == 4  # 4 distinct watches in events
        assert result["events"] == 8
        assert result["users"] == 3


# ── get_available_tiers tests ──

class TestGetAvailableTiers:
    def test_excludes_deprecated(self, test_db):
        tiers = get_available_tiers(test_db)
        assert "Legacy" not in tiers

    def test_includes_active_tiers(self, test_db):
        tiers = get_available_tiers(test_db)
        assert "Bronze" in tiers
        assert "Silver" in tiers
        assert "Gold" in tiers
        assert "Icy" in tiers

    def test_ordered_by_price(self, test_db):
        tiers = get_available_tiers(test_db)
        # Test DB has: Bronze=50, Silver=100 (no pricing), Gold=500, Icy=1000 (no pricing)
        # Tiers without pricing come first (cost=0), then by price ascending
        assert tiers.index("Bronze") < tiers.index("Gold")
