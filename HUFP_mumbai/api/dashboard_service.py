"""
Aggregated telemetry dashboard: DB + Open-Meteo + neural core + heuristics.
Single response shape for citizen/admin tactical UI.
"""
from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

import httpx
import torch
import torch.nn as nn

# Mumbai reference cell (Santacruz / city centroid)
DEFAULT_LAT = float(os.getenv("SENTINEL_METEO_LAT", "19.0760"))
DEFAULT_LON = float(os.getenv("SENTINEL_METEO_LON", "72.8777"))

OPEN_METEO_URL = "https://api.open-meteo.com/v1/forecast"

# Tactical nodes for map (until DB/geo endpoint exists)
_TACTICAL_NODES: List[Dict[str, Any]] = [
    {"id": "OUT-BKC", "lat": 19.067, "lng": 72.869, "type": "outfall"},
    {"id": "OUT-MULUND", "lat": 19.155, "lng": 72.948, "type": "outfall"},
    {"id": "PUMP-WORLI", "lat": 18.998, "lng": 72.816, "type": "pump"},
    {"id": "NODE-DHARAVI", "lat": 19.033, "lng": 72.853, "type": "sensor"},
    {"id": "RL-CSMT", "lat": 18.940, "lng": 72.835, "type": "railway"},
    {"id": "RL-BANDRA", "lat": 19.054, "lng": 72.841, "type": "railway"},
]

_PUMPS_BASE: List[Dict[str, Any]] = [
    {"name": "Mithi Main (MIDC)", "capacity": 72, "status": "Nominal"},
    {"name": "Brihanmumbai I-Pump East", "capacity": 68, "status": "Nominal"},
    {"name": "Haji Ali Storm Outfall", "capacity": 81, "status": "Nominal"},
    {"name": "Mahul Transfer Station", "capacity": 55, "status": "Nominal"},
]


async def fetch_open_meteo_current(
    lat: float = DEFAULT_LAT,
    lon: float = DEFAULT_LON,
) -> Optional[Dict[str, Any]]:
    params = {
        "latitude": lat,
        "longitude": lon,
        "current": (
            "temperature_2m,precipitation,relative_humidity_2m,"
            "wind_speed_10m,surface_pressure,soil_moisture_0_to_7cm"
        ),
        "timezone": "Asia/Kolkata",
    }
    try:
        async with httpx.AsyncClient(timeout=4.0) as client:
            r = await client.get(OPEN_METEO_URL, params=params)
            r.raise_for_status()
            return r.json()
    except Exception:
        return None


def _heuristic_lock_frac(
    rainfall_mm: float,
    tide_m: float,
    flood_m: Optional[float],
    soil_moisture: float,
) -> float:
    f = float(flood_m) if flood_m is not None else 0.0
    s = max(0.0, min(1.0, soil_moisture))
    score = (
        min(1.0, rainfall_mm / 95.0) * 0.38
        + min(1.0, tide_m / 4.5) * 0.28
        + min(1.0, f / 2.5) * 0.22
        + (s - 0.35) * 0.35
    )
    return float(max(0.03, min(0.97, score)))


def _neural_predict(
    core: nn.Module,
    vector: List[float],
) -> Tuple[float, float]:
    """Returns raw flood depth estimate and lock fraction in [0, 1]."""
    t = torch.tensor([vector], dtype=torch.float32).unsqueeze(1)
    with torch.no_grad():
        pred = core(t)
    flood = float(pred[0][0])
    lock_raw = float(pred[0][1])
    lock_frac = max(0.0, min(1.0, lock_raw))
    return flood, lock_frac


def _merge_rainfall(db_mm: Optional[float], om_mm: Optional[float]) -> Tuple[float, str]:
    a = float(db_mm) if db_mm is not None else 0.0
    b = float(om_mm) if om_mm is not None else 0.0
    if a > 0 and b > 0:
        return round(max(a, b), 2), "db+open_meteo"
    if a > 0:
        return round(a, 2), "db"
    if b > 0:
        return round(b, 2), "open_meteo"
    return round(max(a, b), 2), "stub"


async def build_telemetry_dashboard(
    sentinel_core: nn.Module,
    *,
    neural_ready: bool,
    db_row: Optional[Dict[str, Any]],
) -> Dict[str, Any]:
    om = await fetch_open_meteo_current()
    cur = (om or {}).get("current") or {}
    prov: Dict[str, str] = {"open_meteo": "unavailable" if not om else "ok"}

    om_precip = cur.get("precipitation")
    om_rh = cur.get("relative_humidity_2m")
    om_wind = cur.get("wind_speed_10m")
    om_pres = cur.get("surface_pressure")
    om_soil = cur.get("soil_moisture_0_to_7cm")

    db_precip = db_row.get("precip_mm_hr") if db_row else None
    rainfall_mm, rain_src = _merge_rainfall(
        float(db_precip) if db_precip is not None else None,
        float(om_precip) if om_precip is not None else None,
    )
    prov["rainfall"] = rain_src

    tide_m = 1.15
    if db_row and db_row.get("tidal_height_m") is not None:
        tide_m = float(db_row["tidal_height_m"])
        prov["tide"] = "db"
    else:
        prov["tide"] = "synthetic_baseline"

    flood_obs = db_row.get("actual_flood_depth_m") if db_row else None

    humidity = float(om_rh) if om_rh is not None else 78.0
    soil_moisture = float(om_soil) if om_soil is not None else 0.42
    wind_kmh = float(om_wind) if om_wind is not None else 12.0
    pressure = float(om_pres) if om_pres is not None else 1013.2
    prov["humidity"] = "open_meteo" if om_rh is not None else "default"
    prov["soil"] = "open_meteo" if om_soil is not None else "default"
    prov["wind"] = "open_meteo" if om_wind is not None else "default"
    prov["pressure"] = "open_meteo" if om_pres is not None else "default"

    flow_scale = 1.0 + min(rainfall_mm, 45.0) / 90.0
    flow_a = round(flow_scale, 3)
    flow_b = round(flow_scale * 0.95, 3)

    vector = [
        rainfall_mm,
        tide_m,
        flow_a,
        flow_b,
        humidity,
        soil_moisture,
        wind_kmh,
        pressure,
    ]

    h_lock = _heuristic_lock_frac(rainfall_mm, tide_m, flood_obs, soil_moisture)
    flood_neural: Optional[float] = None
    lock_neural: Optional[float] = None
    if neural_ready:
        try:
            fd, lf = _neural_predict(sentinel_core, vector)
            flood_neural = round(max(0.0, fd), 3)
            lock_neural = lf
        except Exception:
            neural_ready = False

    trust = os.getenv("SENTINEL_MODEL_TRUST", "neural").lower()
    if not neural_ready:
        trust = "heuristic"
    if trust == "heuristic":
        lock_frac = h_lock
        prov["lock"] = "heuristic"
    elif trust == "blend":
        lock_frac = (
            0.5 * h_lock + 0.5 * lock_neural if lock_neural is not None else h_lock
        )
        prov["lock"] = "blend(neural+heuristic)"
    else:
        lock_frac = lock_neural if lock_neural is not None else h_lock
        prov["lock"] = "neural" if lock_neural is not None else "heuristic_fallback"

    swd_block = round(min(100.0, lock_frac * 100 + rainfall_mm * 0.35), 1)

    hydrology_tensor = {
        "rainfall_mm": round(rainfall_mm, 2),
        "tide_level_m": round(tide_m, 3),
        "swd_blockage_pct": swd_block,
        "wind_speed_kmh": round(wind_kmh, 1),
    }

    xai = {
        "tidal_surge": round(min(100.0, (tide_m / 3.5) * 100), 1),
        "local_rain": round(min(100.0, rainfall_mm * 1.1), 1),
        "soil_sat": round(min(100.0, soil_moisture * 100), 1),
        "drain_block": round(min(100.0, lock_frac * 100), 1),
        "wind_shear": round(min(100.0, (wind_kmh / 100.0) * 100), 1),
    }

    pumps: List[Dict[str, Any]] = []
    for p in _PUMPS_BASE:
        cap = int(p["capacity"])
        if lock_frac > 0.72:
            cap = min(99, cap + 12)
            st = "Overloaded"
        elif lock_frac > 0.45:
            st = "Elevated"
        else:
            st = str(p["status"])
        pumps.append({"name": p["name"], "capacity": cap, "status": st})

    nodes: List[Dict[str, Any]] = []
    for n in _TACTICAL_NODES:
        is_rail = n["type"] == "railway"
        thr = 0.55 if is_rail else 0.62
        status = "Red" if lock_frac >= thr else "Green"
        nodes.append(
            {
                "id": n["id"],
                "lat": n["lat"],
                "lng": n["lng"],
                "type": n["type"],
                "status": status,
            }
        )

    sitreps: List[str] = [
        f"[{datetime.now(timezone.utc).strftime('%H:%MZ')}] HYDRAULIC_INDEX {(lock_frac * 100):.0f}% ({prov['lock']})",
        f"Rainfall field {rainfall_mm:.1f} mm/h ({prov['rainfall']}); tide {tide_m:.2f} m ({prov['tide']}).",
    ]
    if lock_frac > 0.65:
        sitreps.append("WARNING: Elevated combined surge + runoff — verify pump roster.")
    if rainfall_mm > 35:
        sitreps.append("WARNING: Intense rainfall band — nala capacity stress likely.")
    if not om:
        sitreps.append("METEO: Open-Meteo unreachable — hydrology partially defaulted.")

    temp_c: Optional[float] = None
    if cur.get("temperature_2m") is not None:
        temp_c = float(cur["temperature_2m"])

    surface_meteo = {
        "temperature_c": round(temp_c, 1) if temp_c is not None else None,
        "soil_moisture_vol": round(soil_moisture, 4),
        "relative_humidity_pct": round(humidity, 1),
        "wind_speed_kmh": round(wind_kmh, 1),
        "pressure_hpa": round(pressure, 1),
    }

    return {
        "schema_version": 1,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "provenance": prov,
        "surface_meteo": surface_meteo,
        "hydraulic_lock_probability": round(lock_frac, 4),
        "tide_level_m": hydrology_tensor["tide_level_m"],
        "rainfall_intensity": hydrology_tensor["rainfall_mm"],
        "hydrology_tensor": hydrology_tensor,
        "xai": xai,
        "pumps": pumps,
        "nodes": nodes,
        "sitreps": sitreps,
        "inference": {
            "flood_depth_m": flood_neural,
            "lock_probability_pct": round(lock_frac * 100, 2),
            "neural_active": neural_ready and lock_neural is not None,
            "heuristic_lock_frac": round(h_lock, 4),
        },
        "ward_id": db_row.get("ward_id") if db_row else None,
        "status": "ELEVATED" if lock_frac > 0.45 else "NOMINAL",
    }
