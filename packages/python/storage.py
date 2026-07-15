from __future__ import annotations

import json
import os
import sqlite3
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
RUNTIME_DIR = os.getenv("QUANT_HARNESS_RUNTIME_DIR")
DB_DIR = Path(RUNTIME_DIR) if RUNTIME_DIR else Path("/tmp/quant-harness/runtime") if os.getenv("VERCEL") else ROOT / "data" / "runtime"
DB_DIR.mkdir(parents=True, exist_ok=True)
DB_PATH = DB_DIR / "quant_harness.db"


def get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    with get_conn() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS pipeline_runs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                trade_date TEXT NOT NULL,
                source TEXT NOT NULL,
                market_json TEXT NOT NULL,
                report_json TEXT NOT NULL,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS signals (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                run_id INTEGER NOT NULL,
                trade_date TEXT NOT NULL,
                strategy TEXT NOT NULL,
                symbol TEXT NOT NULL,
                name TEXT NOT NULL,
                score REAL NOT NULL,
                risk_level TEXT NOT NULL,
                theme TEXT NOT NULL,
                signal_json TEXT NOT NULL,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(run_id) REFERENCES pipeline_runs(id)
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS validations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                signal_id INTEGER NOT NULL,
                validation_date TEXT NOT NULL,
                return_1d REAL,
                return_3d REAL,
                return_5d REAL,
                outcome_label TEXT NOT NULL,
                note TEXT,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(signal_id) REFERENCES signals(id)
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS paper_positions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                symbol TEXT NOT NULL,
                name TEXT NOT NULL,
                opened_trade_date TEXT NOT NULL,
                entry_price REAL NOT NULL,
                target_weight_pct REAL NOT NULL,
                status TEXT NOT NULL DEFAULT 'open',
                theme TEXT,
                strategy_json TEXT NOT NULL,
                plan_json TEXT NOT NULL,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                closed_trade_date TEXT,
                exit_price REAL,
                realized_return_pct REAL,
                peak_return_pct REAL DEFAULT 0,
                partial_exit_taken INTEGER DEFAULT 0,
                lifecycle_state TEXT DEFAULT 'open'
            )
            """
        )
        existing_columns = {row['name'] for row in conn.execute("PRAGMA table_info(paper_positions)").fetchall()}
        if 'peak_return_pct' not in existing_columns:
            conn.execute("ALTER TABLE paper_positions ADD COLUMN peak_return_pct REAL DEFAULT 0")
        if 'partial_exit_taken' not in existing_columns:
            conn.execute("ALTER TABLE paper_positions ADD COLUMN partial_exit_taken INTEGER DEFAULT 0")
        if 'lifecycle_state' not in existing_columns:
            conn.execute("ALTER TABLE paper_positions ADD COLUMN lifecycle_state TEXT DEFAULT 'open'")
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS paper_trades (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                trade_date TEXT NOT NULL,
                symbol TEXT NOT NULL,
                name TEXT NOT NULL,
                side TEXT NOT NULL,
                price REAL NOT NULL,
                weight_pct REAL NOT NULL,
                note TEXT,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS paper_trade_attribution (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                trade_date TEXT NOT NULL,
                symbol TEXT NOT NULL,
                name TEXT NOT NULL,
                action TEXT NOT NULL,
                lifecycle_state TEXT,
                reason TEXT,
                return_pct REAL,
                peak_return_pct REAL,
                weight_before_pct REAL,
                weight_after_pct REAL,
                meta_json TEXT,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
            """
        )


def save_pipeline_run(payload: dict[str, Any]) -> int:
    init_db()
    with get_conn() as conn:
        cur = conn.execute(
            "INSERT INTO pipeline_runs (trade_date, source, market_json, report_json) VALUES (?, ?, ?, ?)",
            (
                payload["trade_date"],
                payload["meta"]["source"],
                json.dumps(payload["market"], ensure_ascii=False),
                json.dumps(payload["report"], ensure_ascii=False),
            ),
        )
        run_id = int(cur.lastrowid)
        for signal in payload["signals"]:
            conn.execute(
                """
                INSERT INTO signals (
                    run_id, trade_date, strategy, symbol, name, score, risk_level, theme, signal_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    run_id,
                    payload["trade_date"],
                    signal["strategy"],
                    signal["symbol"],
                    signal["name"],
                    signal["score"],
                    signal["risk_level"],
                    signal["theme"],
                    json.dumps(signal, ensure_ascii=False),
                ),
            )
        return run_id


def list_runs(limit: int = 20) -> list[dict[str, Any]]:
    init_db()
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT id, trade_date, source, created_at FROM pipeline_runs ORDER BY id DESC LIMIT ?",
            (limit,),
        ).fetchall()
        return [dict(row) for row in rows]


def list_signals_by_run(run_id: int) -> list[dict[str, Any]]:
    init_db()
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT id, trade_date, strategy, symbol, name, score, risk_level, theme FROM signals WHERE run_id = ? ORDER BY score DESC",
            (run_id,),
        ).fetchall()
        return [dict(row) for row in rows]


def list_all_signals(limit: int = 500) -> list[dict[str, Any]]:
    init_db()
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT id, run_id, trade_date, strategy, symbol, name, score, risk_level, theme FROM signals ORDER BY id DESC LIMIT ?",
            (limit,),
        ).fetchall()
        return [dict(row) for row in rows]


def list_all_signal_details(limit: int = 500) -> list[dict[str, Any]]:
    init_db()
    with get_conn() as conn:
        rows = conn.execute(
            """
            SELECT
                s.id,
                s.run_id,
                s.trade_date,
                s.strategy,
                s.symbol,
                s.name,
                s.score,
                s.risk_level,
                s.theme,
                s.signal_json,
                pr.source,
                pr.market_json
            FROM signals s
            JOIN pipeline_runs pr ON pr.id = s.run_id
            ORDER BY s.id DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
        items: list[dict[str, Any]] = []
        for row in rows:
            item = dict(row)
            try:
                item['signal'] = json.loads(item.pop('signal_json'))
            except Exception:
                item['signal'] = {}
            try:
                item['market'] = json.loads(item.pop('market_json'))
            except Exception:
                item['market'] = {}
            items.append(item)
        return items


def save_validation(signal_id: int, validation: dict[str, Any]) -> int:
    init_db()
    with get_conn() as conn:
        cur = conn.execute(
            """
            INSERT INTO validations (
                signal_id, validation_date, return_1d, return_3d, return_5d, outcome_label, note
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                signal_id,
                validation["validation_date"],
                validation.get("return_1d"),
                validation.get("return_3d"),
                validation.get("return_5d"),
                validation["outcome_label"],
                validation.get("note", ""),
            ),
        )
        return int(cur.lastrowid)


def list_validations(limit: int = 50) -> list[dict[str, Any]]:
    init_db()
    with get_conn() as conn:
        rows = conn.execute(
            """
            SELECT v.id, s.symbol, s.name, s.strategy, v.validation_date, v.return_1d, v.return_3d, v.return_5d, v.outcome_label
            FROM validations v
            JOIN signals s ON s.id = v.signal_id
            ORDER BY v.id DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
        return [dict(row) for row in rows]


def list_validation_signal_details(limit: int = 500) -> list[dict[str, Any]]:
    init_db()
    with get_conn() as conn:
        rows = conn.execute(
            """
            SELECT
                v.id,
                v.validation_date,
                v.return_1d,
                v.return_3d,
                v.return_5d,
                v.outcome_label,
                v.note,
                s.trade_date,
                s.strategy,
                s.symbol,
                s.name,
                s.score,
                s.risk_level,
                s.theme,
                s.signal_json,
                pr.market_json
            FROM validations v
            JOIN signals s ON s.id = v.signal_id
            JOIN pipeline_runs pr ON pr.id = s.run_id
            ORDER BY v.id DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
        items: list[dict[str, Any]] = []
        for row in rows:
            item = dict(row)
            try:
                item['signal'] = json.loads(item.pop('signal_json'))
            except Exception:
                item['signal'] = {}
            try:
                item['market'] = json.loads(item.pop('market_json'))
            except Exception:
                item['market'] = {}
            items.append(item)
        return items


def save_paper_trade_attribution(payload: dict[str, Any], conn: sqlite3.Connection | None = None) -> int:
    init_db()
    own_conn = conn is None
    active_conn = conn or get_conn()
    try:
        cur = active_conn.execute(
            """
            INSERT INTO paper_trade_attribution (
                trade_date, symbol, name, action, lifecycle_state, reason, return_pct,
                peak_return_pct, weight_before_pct, weight_after_pct, meta_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                payload['trade_date'],
                payload['symbol'],
                payload['name'],
                payload['action'],
                payload.get('lifecycle_state', ''),
                payload.get('reason', ''),
                payload.get('return_pct'),
                payload.get('peak_return_pct'),
                payload.get('weight_before_pct'),
                payload.get('weight_after_pct'),
                json.dumps(payload.get('meta') or {}, ensure_ascii=False),
            ),
        )
        if own_conn:
            active_conn.commit()
        return int(cur.lastrowid)
    finally:
        if own_conn:
            active_conn.close()


def list_paper_trade_attribution(limit: int = 200) -> list[dict[str, Any]]:
    init_db()
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM paper_trade_attribution ORDER BY id DESC LIMIT ?",
            (limit,),
        ).fetchall()
        items: list[dict[str, Any]] = []
        for row in rows:
            item = dict(row)
            try:
                item['meta'] = json.loads(item.pop('meta_json') or '{}')
            except Exception:
                item['meta'] = {}
            items.append(item)
        return items
