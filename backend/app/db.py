from __future__ import annotations

import sqlite3
import threading
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

from app.config import DATABASE_PATH

_lock = threading.Lock()


SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS profiles (
    user_id TEXT PRIMARY KEY,
    risk_tolerance TEXT NOT NULL,
    horizon TEXT NOT NULL,
    capital REAL NOT NULL,
    monthly_investment REAL NOT NULL,
    max_stock_allocation REAL NOT NULL,
    objective TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY (user_id) REFERENCES users(id)
);
CREATE TABLE IF NOT EXISTS portfolio (
    user_id TEXT PRIMARY KEY,
    updated_at TEXT NOT NULL,
    FOREIGN KEY (user_id) REFERENCES users(id)
);
CREATE TABLE IF NOT EXISTS portfolio_holdings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id TEXT NOT NULL,
    symbol TEXT NOT NULL,
    yahoo_symbol TEXT NOT NULL,
    name TEXT,
    quantity REAL NOT NULL,
    avg_price REAL NOT NULL,
    sector TEXT,
    UNIQUE(user_id, yahoo_symbol)
);
CREATE TABLE IF NOT EXISTS watchlist (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id TEXT NOT NULL,
    symbol TEXT NOT NULL,
    yahoo_symbol TEXT NOT NULL,
    name TEXT,
    added_at TEXT NOT NULL,
    UNIQUE(user_id, yahoo_symbol)
);
CREATE TABLE IF NOT EXISTS market_data (
    yahoo_symbol TEXT PRIMARY KEY,
    payload TEXT NOT NULL,
    fetched_at TEXT NOT NULL,
    source TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS news (
    id TEXT PRIMARY KEY,
    yahoo_symbol TEXT,
    title TEXT NOT NULL,
    publisher TEXT,
    url TEXT,
    published_at TEXT,
    sentiment TEXT,
    payload TEXT,
    fetched_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS documents (
    id TEXT PRIMARY KEY,
    yahoo_symbol TEXT,
    title TEXT NOT NULL,
    source TEXT NOT NULL,
    url TEXT,
    doc_type TEXT,
    fetched_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS document_chunks (
    id TEXT PRIMARY KEY,
    document_id TEXT NOT NULL,
    chunk_index INTEGER NOT NULL,
    text TEXT NOT NULL,
    page INTEGER,
    FOREIGN KEY (document_id) REFERENCES documents(id)
);
CREATE TABLE IF NOT EXISTS agent_runs (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    yahoo_symbol TEXT NOT NULL,
    started_at TEXT NOT NULL,
    finished_at TEXT,
    status TEXT NOT NULL,
    simulate_failure TEXT,
    trace TEXT
);
CREATE TABLE IF NOT EXISTS agent_outputs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id TEXT NOT NULL,
    agent TEXT NOT NULL,
    payload TEXT NOT NULL,
    latency_ms REAL,
    status TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS recommendations (
    id TEXT PRIMARY KEY,
    run_id TEXT NOT NULL,
    user_id TEXT NOT NULL,
    yahoo_symbol TEXT NOT NULL,
    action TEXT NOT NULL,
    confidence REAL,
    risk TEXT,
    payload TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS citations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id TEXT NOT NULL,
    agent TEXT,
    source TEXT,
    title TEXT,
    url TEXT,
    snippet TEXT,
    published_at TEXT,
    relevance REAL,
    page INTEGER
);
CREATE TABLE IF NOT EXISTS performance_metrics (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id TEXT,
    name TEXT NOT NULL,
    value REAL,
    unit TEXT,
    recorded_at TEXT NOT NULL,
    notes TEXT
);
CREATE TABLE IF NOT EXISTS api_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    provider TEXT NOT NULL,
    endpoint TEXT,
    ok INTEGER NOT NULL,
    latency_ms REAL,
    error TEXT,
    recorded_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS provider_health (
    provider TEXT PRIMARY KEY,
    status TEXT NOT NULL,
    last_ok_at TEXT,
    last_error TEXT,
    last_latency_ms REAL,
    freshness TEXT
);
"""


def utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


def connect() -> sqlite3.Connection:
    DATABASE_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DATABASE_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


_conn: sqlite3.Connection | None = None


def get_conn() -> sqlite3.Connection:
    global _conn
    if _conn is None:
        _conn = connect()
        _conn.executescript(SCHEMA)
        _seed(_conn)
        _conn.commit()
    return _conn


@contextmanager
def db():
    conn = get_conn()
    with _lock:
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise


def _seed(conn: sqlite3.Connection) -> None:
    now = utcnow()
    row = conn.execute("SELECT id FROM users WHERE id = 'local'").fetchone()
    if row:
        return
    conn.execute(
        "INSERT INTO users (id, name, created_at) VALUES (?, ?, ?)",
        ("local", "Investor", now),
    )
    conn.execute(
        """INSERT INTO profiles (user_id, risk_tolerance, horizon, capital, monthly_investment,
           max_stock_allocation, objective, updated_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        ("local", "moderate", "medium", 500000, 10000, 0.20, "balanced", now),
    )
    conn.execute("INSERT INTO portfolio (user_id, updated_at) VALUES (?, ?)", ("local", now))
    holdings = [
        ("RELIANCE", "RELIANCE.NS", "Reliance Industries", 25, 1180, "Energy"),
        ("TCS", "TCS.NS", "Tata Consultancy Services", 8, 3650, "Information Technology"),
        ("HDFCBANK", "HDFCBANK.NS", "HDFC Bank", 12, 1480, "Financials"),
        ("INFY", "INFY.NS", "Infosys", 10, 1420, "Information Technology"),
    ]
    for h in holdings:
        conn.execute(
            """INSERT INTO portfolio_holdings
               (user_id, symbol, yahoo_symbol, name, quantity, avg_price, sector)
               VALUES ('local', ?, ?, ?, ?, ?, ?)""",
            h,
        )
    watch = [
        ("RELIANCE", "RELIANCE.NS", "Reliance Industries"),
        ("TCS", "TCS.NS", "Tata Consultancy Services"),
        ("INFY", "INFY.NS", "Infosys"),
        ("SBIN", "SBIN.NS", "State Bank of India"),
    ]
    for w in watch:
        conn.execute(
            "INSERT INTO watchlist (user_id, symbol, yahoo_symbol, name, added_at) VALUES ('local', ?, ?, ?, ?)",
            (*w, now),
        )


def log_api(provider: str, endpoint: str, ok: bool, latency_ms: float, error: str | None = None) -> None:
    with db() as conn:
        conn.execute(
            """INSERT INTO api_logs (provider, endpoint, ok, latency_ms, error, recorded_at)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (provider, endpoint, 1 if ok else 0, latency_ms, error, utcnow()),
        )
        status = "connected" if ok else "error"
        conn.execute(
            """INSERT INTO provider_health (provider, status, last_ok_at, last_error, last_latency_ms, freshness)
               VALUES (?, ?, ?, ?, ?, ?)
               ON CONFLICT(provider) DO UPDATE SET
                 status=excluded.status,
                 last_ok_at=CASE WHEN excluded.status='connected' THEN excluded.last_ok_at ELSE last_ok_at END,
                 last_error=excluded.last_error,
                 last_latency_ms=excluded.last_latency_ms
            """,
            (provider, status, utcnow() if ok else None, error, latency_ms, "delayed" if ok else "unavailable"),
        )
