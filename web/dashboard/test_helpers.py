"""Tests for helper functions, user data functions, and API endpoints in dashboard/app.py."""

import sqlite3
import json
import os
import sys

import pytest

# Add project root to path so we can import the dashboard module
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dashboard.app import (
    app,
    slugify,
    format_money,
    format_pct,
    rarity_color,
    validate_price_value,
    ensure_user_data_table,
    save_watch_user_data,
    get_watch_user_data,
    load_sql_query,
)


# ── slugify tests ──


class TestSlugify:
    def test_normal_name(self):
        assert slugify("Rolex Submariner") == "rolex-submariner"

    def test_special_characters(self):
        assert slugify("Omega Seamaster (Co-Axial)") == "omega-seamaster-co-axial"

    def test_multiple_spaces(self):
        assert slugify("  Casio  G-Shock  ") == "casio-g-shock"

    def test_underscores(self):
        assert slugify("Grand_Seiko_Spring") == "grand-seiko-spring"


# ── format_money tests ──


class TestFormatMoney:
    def test_normal_value(self):
        assert format_money(1234.56) == "$1,234.56"

    def test_zero(self):
        assert format_money(0) == "$0.00"

    def test_large_value(self):
        assert format_money(150000) == "$150,000.00"

    def test_none_passthrough(self):
        assert format_money(None) is None


# ── format_pct tests ──


class TestFormatPct:
    def test_normal_value(self):
        assert format_pct(12.34) == "12.34%"

    def test_zero(self):
        assert format_pct(0) == "0.00%"

    def test_none_passthrough(self):
        assert format_pct(None) is None


# ── rarity_color tests ──


class TestRarityColor:
    def test_quartz(self):
        assert rarity_color("quartz") == "#9ca3af"

    def test_grail(self):
        assert rarity_color("grail") == "#eab308"

    def test_unknown_key(self):
        assert rarity_color("unknown") == "#6b7280"


# ── validate_price_value tests ──


class TestValidatePriceValue:
    def test_valid_number(self):
        val, err = validate_price_value(1200.50)
        assert val == 1200.50
        assert err is None

    def test_zero(self):
        val, err = validate_price_value(0)
        assert val == 0.0
        assert err is None

    def test_negative(self):
        val, err = validate_price_value(-100)
        assert val is None
        assert err is not None

    def test_string(self):
        val, err = validate_price_value("abc")
        assert val is None
        assert err is not None

    def test_none(self):
        val, err = validate_price_value(None)
        assert val is None
        assert err is None

    def test_empty_string(self):
        val, err = validate_price_value("")
        assert val is None
        assert err is None


# ── ensure_user_data_table tests ──


class TestEnsureUserDataTable:
    def test_creates_table_on_fresh_db(self, tmp_path):
        db_path = str(tmp_path / "fresh.db")
        # Create a fresh empty database
        conn = sqlite3.connect(db_path)
        conn.close()

        ensure_user_data_table(db_path)

        conn = sqlite3.connect(db_path)
        cursor = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='user_watch_data'"
        )
        assert cursor.fetchone() is not None
        conn.close()

    def test_idempotent_on_existing_db(self, tmp_path):
        db_path = str(tmp_path / "existing.db")
        conn = sqlite3.connect(db_path)
        conn.close()

        # Call twice — should not raise
        ensure_user_data_table(db_path)
        ensure_user_data_table(db_path)

        conn = sqlite3.connect(db_path)
        cursor = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='user_watch_data'"
        )
        assert cursor.fetchone() is not None
        conn.close()


# ── save_watch_user_data / get_watch_user_data tests ──


@pytest.fixture
def user_data_db(tmp_path):
    """Create a test database with the user_watch_data table."""
    db_path = str(tmp_path / "userdata.db")
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute(
        """
        CREATE TABLE user_watch_data (
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
    conn.commit()
    yield conn
    conn.close()


class TestSaveWatchUserData:
    def test_insert_new_data(self, user_data_db):
        result = save_watch_user_data(
            user_data_db, "Rolex Submariner", msrp=12500.0, market_value=9800.0, notes="Mint condition"
        )
        assert result["item_name"] == "Rolex Submariner"
        assert result["msrp"] == 12500.0
        assert result["market_value"] == 9800.0
        assert result["notes"] == "Mint condition"

        # Verify in DB
        data = get_watch_user_data(user_data_db, "Rolex Submariner")
        assert data["msrp"] == 12500.0
        assert data["market_value"] == 9800.0
        assert data["notes"] == "Mint condition"

    def test_update_existing_data(self, user_data_db):
        save_watch_user_data(user_data_db, "Omega Seamaster", msrp=5000.0)
        save_watch_user_data(user_data_db, "Omega Seamaster", msrp=5500.0, market_value=4800.0)

        data = get_watch_user_data(user_data_db, "Omega Seamaster")
        assert data["msrp"] == 5500.0
        assert data["market_value"] == 4800.0

    def test_clear_individual_fields(self, user_data_db):
        save_watch_user_data(
            user_data_db, "Seiko Presage", msrp=400.0, market_value=350.0, notes="Nice"
        )
        # Clear msrp but keep others
        save_watch_user_data(
            user_data_db, "Seiko Presage", msrp=None, market_value=350.0, notes="Nice"
        )

        data = get_watch_user_data(user_data_db, "Seiko Presage")
        assert data["msrp"] is None
        assert data["market_value"] == 350.0
        assert data["notes"] == "Nice"

    def test_clear_all_fields_deletes_row(self, user_data_db):
        save_watch_user_data(user_data_db, "Casio G-Shock", msrp=150.0)
        save_watch_user_data(user_data_db, "Casio G-Shock", msrp=None, market_value=None, notes=None)

        data = get_watch_user_data(user_data_db, "Casio G-Shock")
        assert data is None


class TestGetWatchUserData:
    def test_returns_data_for_existing_watch(self, user_data_db):
        save_watch_user_data(user_data_db, "Rolex Daytona", msrp=30000.0, notes="Grail watch")
        data = get_watch_user_data(user_data_db, "Rolex Daytona")
        assert data is not None
        assert data["msrp"] == 30000.0
        assert data["notes"] == "Grail watch"

    def test_returns_none_for_missing_watch(self, user_data_db):
        data = get_watch_user_data(user_data_db, "Nonexistent Watch")
        assert data is None


# ── load_sql_query tests ──


class TestLoadSqlQuery:
    def test_loads_profit_by_tier(self):
        sql = load_sql_query("profit-by-tier")
        assert len(sql) > 0

    def test_loads_rarity_drift_by_period(self):
        sql = load_sql_query("rarity-drift-by-period")
        assert len(sql) > 0

    def test_loads_top_users(self):
        sql = load_sql_query("top-users")
        assert len(sql) > 0

    def test_loads_user_loss(self):
        sql = load_sql_query("user-loss")
        assert len(sql) > 0

    def test_loads_watch_drops_per_tier(self):
        sql = load_sql_query("watch-drops-per-tier")
        assert len(sql) > 0

    def test_raises_for_unknown_query(self):
        with pytest.raises(ValueError, match="Unknown query"):
            load_sql_query("nonexistent-query")


# ── API endpoint tests ──


@pytest.fixture
def api_db(tmp_path):
    """Create a test database with all required tables for API testing."""
    db_path = str(tmp_path / "api_test.db")
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row

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

    # Insert a watch in events so the slug resolver can find it
    conn.execute("INSERT INTO watches VALUES ('Rolex Submariner', 12000.0, '', '', '')")
    conn.execute("""
        INSERT INTO events VALUES
        ('e1', 'user1', 'twitch', 'Gold Box', 'Gold', 'gold-box',
         'Rolex Submariner', 12000.0, 'tourbillon', '', '',
         '2024-01-01T00:00:00Z', '2024-01-01T00:00:00Z')
    """)

    conn.commit()
    conn.close()

    # Configure the Flask app
    app.config["DB_PATH"] = db_path
    app.config["TESTING"] = True

    yield db_path


@pytest.fixture
def client(api_db):
    """Flask test client."""
    with app.test_client() as c:
        yield c


class TestApiEndpoints:
    def test_save_msrp_successfully(self, client, api_db):
        resp = client.post(
            "/api/watch/rolex-submariner/user-data",
            data=json.dumps({"msrp": 12500.0}),
            content_type="application/json",
        )
        data = resp.get_json()
        assert resp.status_code == 200
        assert data["ok"] is True
        assert data["msrp"] == 12500.0

    def test_save_market_value_successfully(self, client, api_db):
        resp = client.post(
            "/api/watch/rolex-submariner/user-data",
            data=json.dumps({"market_value": 9800.0}),
            content_type="application/json",
        )
        data = resp.get_json()
        assert resp.status_code == 200
        assert data["ok"] is True
        assert data["market_value"] == 9800.0

    def test_save_notes_successfully(self, client, api_db):
        resp = client.post(
            "/api/watch/rolex-submariner/user-data",
            data=json.dumps({"notes": "Great daily driver"}),
            content_type="application/json",
        )
        data = resp.get_json()
        assert resp.status_code == 200
        assert data["ok"] is True
        assert data["notes"] == "Great daily driver"

    def test_clear_fields(self, client, api_db):
        # First save some data
        client.post(
            "/api/watch/rolex-submariner/user-data",
            data=json.dumps({"msrp": 12500.0, "market_value": 9800.0, "notes": "test"}),
            content_type="application/json",
        )
        # Then clear all fields
        resp = client.post(
            "/api/watch/rolex-submariner/user-data",
            data=json.dumps({"msrp": None, "market_value": None, "notes": None}),
            content_type="application/json",
        )
        data = resp.get_json()
        assert resp.status_code == 200
        assert data["ok"] is True
        assert data["msrp"] is None
        assert data["market_value"] is None
        assert data["notes"] is None

    def test_validation_error_negative_msrp(self, client, api_db):
        resp = client.post(
            "/api/watch/rolex-submariner/user-data",
            data=json.dumps({"msrp": -100}),
            content_type="application/json",
        )
        data = resp.get_json()
        assert resp.status_code == 400
        assert data["ok"] is False
        assert "MSRP" in data["error"]

    def test_validation_error_non_numeric_market_value(self, client, api_db):
        resp = client.post(
            "/api/watch/rolex-submariner/user-data",
            data=json.dumps({"market_value": "abc"}),
            content_type="application/json",
        )
        data = resp.get_json()
        assert resp.status_code == 400
        assert data["ok"] is False
        assert "Market Value" in data["error"]

    def test_404_for_nonexistent_watch(self, client, api_db):
        resp = client.post(
            "/api/watch/nonexistent-watch/user-data",
            data=json.dumps({"msrp": 100}),
            content_type="application/json",
        )
        data = resp.get_json()
        assert resp.status_code == 404
        assert data["ok"] is False
        assert "not found" in data["error"].lower()

    def test_invalid_json_body(self, client, api_db):
        resp = client.post(
            "/api/watch/rolex-submariner/user-data",
            data="not json at all",
            content_type="application/json",
        )
        data = resp.get_json()
        assert resp.status_code == 400
        assert data["ok"] is False
        assert "Invalid JSON" in data["error"]
