import sqlite3
from datetime import datetime, timezone

DB_PATH = "trading_log.db"


def get_connection() -> sqlite3.Connection:
    con = sqlite3.connect(DB_PATH, check_same_thread=False)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA journal_mode=WAL")
    return con


def init_db():
    con = get_connection()
    con.execute("""
        CREATE TABLE IF NOT EXISTS trade_events (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp   TEXT    NOT NULL,
            node        TEXT    NOT NULL,
            model       TEXT    NOT NULL,
            event_type  TEXT    NOT NULL,
            message     TEXT    NOT NULL,
            symbol      TEXT,
            spread_pct  REAL,
            profit_usdt REAL
        )
    """)
    con.commit()
    con.close()


def log_event(
    node: str,
    model: str,
    event_type: str,
    message: str,
    symbol: str = None,
    spread_pct: float = None,
    profit_usdt: float = None,
):
    con = get_connection()
    con.execute(
        """INSERT INTO trade_events
           (timestamp, node, model, event_type, message, symbol, spread_pct, profit_usdt)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            datetime.now(timezone.utc).isoformat(),
            node,
            model,
            event_type,
            message,
            symbol,
            spread_pct,
            profit_usdt,
        ),
    )
    con.commit()
    con.close()
