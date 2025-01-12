"""
SQLite access for the Mumbai coastal vault — shared by FastAPI routes and tooling.
"""
from __future__ import annotations

import os
import sqlite3
from pathlib import Path
from typing import Any, Dict, List, Optional

_REPO_ROOT = Path(__file__).resolve().parent.parent


def vault_db_path() -> Path:
    p = os.getenv("SENTINEL_VAULT_PATH")
    if p:
        return Path(p).expanduser()
    return Path(__file__).resolve().parent.parent / "data" / "mumbai_coastal_vault.db"


def _connect() -> sqlite3.Connection:
    path = vault_db_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path), timeout=5.0)
    conn.row_factory = sqlite3.Row
    return conn


def ensure_schema() -> None:
    """Idempotent schema (matches init_mumbai_vault.py + emergency ingest)."""
    conn = _connect()
    try:
        cur = conn.cursor()
        cur.executescript(
            """
            CREATE TABLE IF NOT EXISTS ward_topography (
                ward_id TEXT PRIMARY KEY,
                ward_name TEXT,
                avg_elevation_m REAL,
                impermeability_index REAL,
                drainage_capacity_m3_s REAL,
                distance_to_coast_m REAL
            );
            CREATE TABLE IF NOT EXISTS telemetry_mesh (
                timestamp DATETIME,
                ward_id TEXT,
                precip_mm_hr REAL,
                cumulative_rain_24h REAL,
                tidal_height_m REAL,
                sar_vh_backscatter REAL,
                actual_flood_depth_m REAL,
                PRIMARY KEY (timestamp, ward_id),
                FOREIGN KEY(ward_id) REFERENCES ward_topography(ward_id)
            );
            CREATE INDEX IF NOT EXISTS idx_time_ward ON telemetry_mesh(timestamp, ward_id);
            CREATE TABLE IF NOT EXISTS emergency_last_known (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                lat REAL NOT NULL,
                lng REAL NOT NULL,
                status TEXT,
                client_note TEXT,
                received_at DATETIME DEFAULT CURRENT_TIMESTAMP
            );
            """
        )
        conn.commit()
    finally:
        conn.close()


def _row_to_dict(row: sqlite3.Row) -> Dict[str, Any]:
    return {k: row[k] for k in row.keys()}


def fetch_latest_telemetry_row() -> Optional[Dict[str, Any]]:
    if not vault_db_path().is_file():
        return None
    conn = _connect()
    try:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT * FROM telemetry_mesh
            ORDER BY datetime(timestamp) DESC
            LIMIT 1
            """
        )
        row = cur.fetchone()
        return _row_to_dict(row) if row else None
    finally:
        conn.close()


def fetch_telemetry_stats() -> Dict[str, Any]:
    if not vault_db_path().is_file():
        return {"count": 0, "avg_precip": None, "avg_flood": None, "latest_ts": None}
    conn = _connect()
    try:
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) AS c FROM telemetry_mesh")
        count = int(cur.fetchone()[0])
        cur.execute(
            """
            SELECT
                AVG(precip_mm_hr) AS ap,
                AVG(actual_flood_depth_m) AS af,
                MAX(timestamp) AS lt
            FROM telemetry_mesh
            """
        )
        row = cur.fetchone()
        return {
            "count": count,
            "avg_precip": row[0],
            "avg_flood": row[1],
            "latest_ts": row[2],
        }
    finally:
        conn.close()


def fetch_ward_summaries() -> List[Dict[str, Any]]:
    if not vault_db_path().is_file():
        return []
    conn = _connect()
    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT ward_id, ward_name, avg_elevation_m, drainage_capacity_m3_s FROM ward_topography ORDER BY ward_id"
        )
        wards = cur.fetchall()
        out: List[Dict[str, Any]] = []
        for wid, wname, elev, cap in wards:
            cur.execute(
                """
                SELECT precip_mm_hr, tidal_height_m, actual_flood_depth_m,
                       sar_vh_backscatter, timestamp
                FROM telemetry_mesh
                WHERE ward_id = ?
                ORDER BY datetime(timestamp) DESC
                LIMIT 1
                """,
                (wid,),
            )
            tr = cur.fetchone()
            out.append(
                {
                    "ward_id": wid,
                    "ward_name": wname,
                    "avg_elevation_m": elev,
                    "drainage_capacity_m3_s": cap,
                    "precip_mm_hr": tr[0] if tr else None,
                    "tidal_height_m": tr[1] if tr else None,
                    "actual_flood_depth_m": tr[2] if tr else None,
                    "sar_vh_backscatter": tr[3] if tr else None,
                    "timestamp": tr[4] if tr else None,
                }
            )
        return out
    finally:
        conn.close()


def insert_emergency_beacon(lat: float, lng: float, status: Optional[str], client_note: Optional[str]) -> int:
    ensure_schema()
    conn = _connect()
    try:
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO emergency_last_known (lat, lng, status, client_note)
            VALUES (?, ?, ?, ?)
            """,
            (lat, lng, status, client_note),
        )
        conn.commit()
        return int(cur.lastrowid)
    finally:
        conn.close()


def add_citizen_pin(lat: float, lng: float, condition: str) -> int:
    """Adds a citizen-reported pin to the emergency matrix."""
    ensure_schema()
    conn = _connect()
    try:
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO emergency_last_known (lat, lng, status, client_note)
            VALUES (?, ?, ?, ?)
            """,
            (lat, lng, f"CITIZEN_REPORT: {condition}", "Public Safety Pin Drop"),
        )
        conn.commit()
        return int(cur.lastrowid)
    finally:
        conn.close()


def fetch_citizen_pins() -> List[Dict[str, Any]]:
    """Fetches recent citizen pins for global visualization."""
    if not vault_db_path().is_file():
        return []
    conn = _connect()
    try:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT lat, lng, status, received_at 
            FROM emergency_last_known 
            WHERE status LIKE 'CITIZEN_REPORT:%'
            ORDER BY datetime(received_at) DESC
            LIMIT 50
            """
        )
        rows = cur.fetchall()
        return [_row_to_dict(r) for r in rows]
    finally:
        conn.close()
