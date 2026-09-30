"""SQLite storage for the portfolio and saved scan results."""

from __future__ import annotations

import json
import sqlite3
import threading
from datetime import datetime, timezone
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS holdings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    market TEXT NOT NULL,
    ticker TEXT NOT NULL,
    shares REAL NOT NULL,
    cost REAL NOT NULL,          -- average cost per share
    note TEXT DEFAULT '',
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS scans (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    market TEXT NOT NULL,
    run_at TEXT NOT NULL,
    results TEXT NOT NULL,       -- JSON list of signals
    errors TEXT NOT NULL DEFAULT '[]'
);
"""


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class Store:
    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        with self._conn() as c:
            c.executescript(SCHEMA)

    def _conn(self):
        c = sqlite3.connect(self.path)
        c.row_factory = sqlite3.Row
        return c

    # holdings
    def holdings(self) -> list[dict]:
        with self._conn() as c:
            return [dict(r) for r in c.execute("SELECT * FROM holdings ORDER BY market, ticker")]

    def add_holding(self, market: str, ticker: str, shares: float, cost: float, note: str = "") -> int:
        with self._lock, self._conn() as c:
            cur = c.execute("INSERT INTO holdings (market, ticker, shares, cost, note, created_at) "
                            "VALUES (?, ?, ?, ?, ?, ?)",
                            (market, ticker.upper().strip(), shares, cost, note, now_iso()))
            return cur.lastrowid

    def update_holding(self, hid: int, shares: float, cost: float, note: str = ""):
        with self._lock, self._conn() as c:
            c.execute("UPDATE holdings SET shares=?, cost=?, note=? WHERE id=?", (shares, cost, note, hid))

    def delete_holding(self, hid: int):
        with self._lock, self._conn() as c:
            c.execute("DELETE FROM holdings WHERE id=?", (hid,))

    # scans
    def save_scan(self, market: str, results: list[dict], errors: list[str]):
        with self._lock, self._conn() as c:
            c.execute("INSERT INTO scans (market, run_at, results, errors) VALUES (?, ?, ?, ?)",
                      (market, now_iso(), json.dumps(results, default=str), json.dumps(errors)))
            c.execute("DELETE FROM scans WHERE market=? AND id NOT IN "
                      "(SELECT id FROM scans WHERE market=? ORDER BY id DESC LIMIT 20)", (market, market))

    def latest_scan(self, market: str) -> dict | None:
        with self._conn() as c:
            r = c.execute("SELECT * FROM scans WHERE market=? ORDER BY id DESC LIMIT 1", (market,)).fetchone()
        if not r:
            return None
        return {"market": r["market"], "run_at": r["run_at"], "results": json.loads(r["results"]),
                "errors": json.loads(r["errors"])}
