import pytest
import sqlite3
import os
from unittest.mock import patch
from src.db import init_db, log_event, get_connection

TEST_DB_PATH = "test_trading_log.db"


@pytest.fixture(autouse=True)
def setup_teardown_db():
    """Fixture to patch DB path and clean up after tests."""
    with patch("src.db.DB_PATH", TEST_DB_PATH):
        if os.path.exists(TEST_DB_PATH):
            os.remove(TEST_DB_PATH)
        init_db()
        yield
        if os.path.exists(TEST_DB_PATH):
            os.remove(TEST_DB_PATH)


def test_init_db():
    """Test database initialization."""
    con = sqlite3.connect(TEST_DB_PATH)
    cursor = con.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='trade_events'")
    table = cursor.fetchone()
    con.close()
    assert table is not None


def test_log_event():
    """Test logging an event."""
    log_event(node="test", model="test-model", event_type="TEST", message="hello world", profit_usdt=10.5)
    
    con = sqlite3.connect(TEST_DB_PATH)
    con.row_factory = sqlite3.Row
    rows = con.execute("SELECT * FROM trade_events").fetchall()
    con.close()

    assert len(rows) == 1
    assert rows[0]["message"] == "hello world"
    assert rows[0]["profit_usdt"] == 10.5