"""SQLite persistence foundation (PostgreSQL-compatible standard SQL).

Stores instrument metadata, effective-dated exchange transfers, cached
historical OHLCV bars, FX reference rates, portfolio holdings, and provider logs.
"""

from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator, Optional

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS instruments (
    instrument_id TEXT PRIMARY KEY,
    ticker TEXT NOT NULL,
    exchange_mic TEXT NOT NULL,
    exchange_acronym TEXT NOT NULL,
    company_name TEXT NOT NULL,
    country TEXT NOT NULL,
    currency TEXT NOT NULL,
    sector TEXT NOT NULL,
    industry TEXT NOT NULL,
    asset_type TEXT NOT NULL,
    timezone TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS exchange_transfers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ticker TEXT NOT NULL,
    from_mic TEXT NOT NULL,
    to_mic TEXT NOT NULL,
    last_old_date TEXT NOT NULL,
    effective_date TEXT NOT NULL,
    circular_reference TEXT NOT NULL,
    UNIQUE(ticker, from_mic, to_mic, effective_date)
);

CREATE TABLE IF NOT EXISTS ohlcv_cache (
    instrument_id TEXT NOT NULL,
    interval TEXT NOT NULL,
    bar_timestamp TEXT NOT NULL,
    open REAL NOT NULL,
    high REAL NOT NULL,
    low REAL NOT NULL,
    close REAL NOT NULL,
    adjusted_close REAL,
    volume INTEGER NOT NULL,
    provider TEXT NOT NULL,
    data_status TEXT NOT NULL,
    retrieved_at TEXT NOT NULL,
    PRIMARY KEY (instrument_id, interval, bar_timestamp, provider)
);

CREATE TABLE IF NOT EXISTS fx_reference_rates (
    base_currency TEXT NOT NULL,
    quote_currency TEXT NOT NULL,
    reference_date TEXT NOT NULL,
    rate REAL NOT NULL,
    provider TEXT NOT NULL,
    retrieved_at TEXT NOT NULL,
    PRIMARY KEY (base_currency, quote_currency, reference_date, provider)
);

CREATE TABLE IF NOT EXISTS provider_audit_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    provider TEXT NOT NULL,
    endpoint TEXT NOT NULL,
    status_code INTEGER,
    data_status TEXT NOT NULL,
    message TEXT,
    recorded_at TEXT NOT NULL
);
"""


class DatabaseManager:
    def __init__(self, db_path: str) -> None:
        self.db_path = db_path
        self._mem_conn: Optional[sqlite3.Connection] = None
        if db_path == ":memory:":
            self._mem_conn = sqlite3.connect(":memory:", check_same_thread=False)
            self._mem_conn.row_factory = sqlite3.Row
        else:
            Path(db_path).parent.mkdir(parents=True, exist_ok=True)

    @contextmanager
    def connect(self) -> Iterator[sqlite3.Connection]:
        if self._mem_conn is not None:
            try:
                yield self._mem_conn
                self._mem_conn.commit()
            except Exception:
                self._mem_conn.rollback()
                raise
            return

        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    def init_db(self) -> None:
        with self.connect() as conn:
            conn.executescript(SCHEMA_SQL)

    def health_check(self) -> bool:
        try:
            with self.connect() as conn:
                conn.execute("SELECT 1").fetchone()
            return True
        except sqlite3.Error:
            return False
