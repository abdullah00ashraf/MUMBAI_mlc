"""
SENTINEL HUFP V7 — OSM Evacuation Node Ingestion Pipeline
Script:  09_osm_evacuation_ingester.py
Purpose: Query OpenStreetMap Overpass API for verified Greater Mumbai infrastructure
         (high-rises, schools, hospitals, police stations) and persist as GeoJSON
         and an optimised columnar Parquet dataset for rapid FastAPI serving.
"""

import json
import logging
import os
import time
import requests
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
from pathlib import Path

# ── Logging ─────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
log = logging.getLogger("OSM_INGESTER")

# ── Paths ────────────────────────────────────────────────────────────────────
REPO_ROOT   = Path(__file__).resolve().parent
DATA_DIR    = REPO_ROOT / "data"
GEOJSON_OUT = DATA_DIR / "evacuation_nodes.geojson"
PARQUET_OUT = DATA_DIR / "evacuation_nodes.parquet"
DATA_DIR.mkdir(parents=True, exist_ok=True)

# ── Greater Mumbai Bounding Box ──────────────────────────────────────────────
# south, west, north, east
BBOX = (18.85, 72.75, 19.35, 73.10)

# ── Overpass endpoints (mirrors for fallback) ────────────────────────────────
OVERPASS_URLS = [
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
    "https://maps.mail.ru/osm/tools/overpass/api/interpreter",
]

# ── Evacuation Category Schema ───────────────────────────────────────────────
CATEGORY_META = {
    "highrise"  : {"label": "High-Rise Vertical Shelter", "capacity": 800,  "status": "Active / Secure"},
    "school"    : {"label": "Reinforced School Shelter",  "capacity": 500,  "status": "Active / Secure"},
    "hospital"  : {"label": "Emergency Medical Zone",     "capacity": 300,  "status": "Active / Critical"},
    "police"    : {"label": "Municipal Control Point",    "capacity": 150,  "status": "Active / Secure"},
}

# Base Mumbai terrain elevation estimate (metres ASL) when not in OSM tags
BASE_TERRAIN_ELEVATION_M = 8.0
FLOOR_HEIGHT_M           = 3.0


def build_overpass_query(bbox: tuple) -> str:
    s, w, n, e = bbox
    bb = f"{s},{w},{n},{e}"
    return f"""
[out:json][timeout:60];
(
  node["building:levels"~"^(1[0-9]|[2-9][0-9]|[0-9]{{3,}})$"]({bb});
  way ["building:levels"~"^(1[0-9]|[2-9][0-9]|[0-9]{{3,}})$"]({bb});
  node["amenity"="school"]({bb});
  way ["amenity"="school"]({bb});
  node["amenity"="hospital"]({bb});
  way ["amenity"="hospital"]({bb});
  node["amenity"="police"]({bb});
  way ["amenity"="police"]({bb});
);
out center tags;
"""


def query_overpass(query: str) -> dict:
    """Try each mirror until one responds."""
    for url in OVERPASS_URLS:
        try:
            log.info(f"Querying Overpass mirror: {url}")
            resp = requests.post(url, data={"data": query}, timeout=75)
            resp.raise_for_status()
            data = resp.json()
            log.info(f"  → {len(data.get('elements', []))} elements received.")
            return data
        except Exception as exc:
            log.warning(f"  Mirror failed ({url}): {exc}")
            time.sleep(2)
    raise RuntimeError("All Overpass mirrors failed. Check internet connectivity.")


def classify_element(tags: dict) -> str | None:
    amenity = tags.get("amenity", "")
    if amenity == "hospital":
        return "hospital"
    if amenity == "police":
        return "police"
    if amenity == "school":
        return "school"
    levels = tags.get("building:levels", "")
    try:
        if int(levels) >= 10:
            return "highrise"
    except (ValueError, TypeError):
        pass
    return None


def extract_coordinates(el: dict) -> tuple[float, float] | None:
    """Return (lon, lat) for node or way-centre."""
    if el["type"] == "node":
        return el.get("lon"), el.get("lat")
    if el["type"] == "way" and "center" in el:
        c = el["center"]
        return c.get("lon"), c.get("lat")
    return None, None


def compute_elevation(tags: dict, category: str) -> float:
    """Estimate structural elevation ASL."""
    levels = 0
    try:
        levels = int(tags.get("building:levels", 0))
    except (ValueError, TypeError):
        pass
    # Elevation = terrain base + floors × floor height
    return round(BASE_TERRAIN_ELEVATION_M + levels * FLOOR_HEIGHT_M, 1)


def build_geojson(elements: list) -> dict:
    features = []
    seen_ids = set()

    for el in elements:
        tags = el.get("tags", {})
        category = classify_element(tags)
        if not category:
            continue

        lon, lat = extract_coordinates(el)
        if lon is None or lat is None:
            continue

        uid = f"{el['type']}-{el['id']}"
        if uid in seen_ids:
            continue
        seen_ids.add(uid)

        meta    = CATEGORY_META[category]
        elev    = compute_elevation(tags, category)
        name    = (
            tags.get("name:en")
            or tags.get("name")
            or f"{meta['label']} #{el['id']}"
        )

        feature = {
            "type": "Feature",
            "geometry": {"type": "Point", "coordinates": [lon, lat]},
            "properties": {
                "id"        : uid,
                "name"      : name,
                "category"  : category,
                "label"     : meta["label"],
                "elevation_asl_m": elev,
                "capacity"  : meta["capacity"],
                "status"    : meta["status"],
                "levels"    : tags.get("building:levels", "N/A"),
                "osm_id"    : el["id"],
            },
        }
        features.append(feature)

    return {"type": "FeatureCollection", "features": features}


def save_geojson(geojson: dict, path: Path) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(geojson, f, ensure_ascii=False, indent=2)
    log.info(f"GeoJSON saved → {path}  ({len(geojson['features'])} features)")


def save_parquet(geojson: dict, path: Path) -> None:
    rows = []
    for feat in geojson["features"]:
        props = feat["properties"]
        lon, lat = feat["geometry"]["coordinates"]
        rows.append({
            "id"              : props["id"],
            "name"            : props["name"],
            "category"        : props["category"],
            "label"           : props["label"],
            "lon"             : float(lon),
            "lat"             : float(lat),
            "elevation_asl_m" : float(props["elevation_asl_m"]),
            "capacity"        : int(props["capacity"]),
            "status"          : props["status"],
            "levels"          : str(props["levels"]),
            "osm_id"          : int(props["osm_id"]),
        })

    if not rows:
        log.warning("No rows to write — Parquet skipped.")
        return

    df = pd.DataFrame(rows)
    table = pa.Table.from_pandas(df)
    pq.write_table(table, path, compression="snappy")
    log.info(f"Parquet saved  → {path}  ({len(rows)} rows)")


def generate_fallback_nodes() -> dict:
    """Synthetic fallback dataset if Overpass is unreachable."""
    log.warning("Generating synthetic fallback evacuation dataset for Mumbai.")
    nodes = [
        ("node-fb-001", "Nariman Point High-Rise Complex", "highrise", 18.925, 72.823, 20, 800),
        ("node-fb-002", "CSMT Heritage Shelter Zone",      "highrise", 18.940, 72.835, 15, 600),
        ("node-fb-003", "KEM Hospital Emergency Zone",     "hospital", 18.989, 72.841,  4, 300),
        ("node-fb-004", "Lilavati Hospital – Bandra",      "hospital", 19.049, 72.826,  6, 250),
        ("node-fb-005", "Dharavi Municipal School",        "school",   19.041, 72.856,  3, 500),
        ("node-fb-006", "Andheri Police Station",          "police",   19.113, 72.868,  2, 150),
        ("node-fb-007", "Worli Sea Face Highrise",         "highrise", 19.011, 72.815, 28, 900),
        ("node-fb-008", "Bandra-Kurla Complex Office Hub", "highrise", 19.066, 72.868, 22, 700),
        ("node-fb-009", "Powai Hospital",                  "hospital", 19.119, 72.905,  5, 280),
        ("node-fb-010", "Colaba Police HQ",                "police",   18.905, 72.815,  3, 180),
        ("node-fb-011", "Juhu Airport Side School",        "school",   19.096, 72.837,  2, 420),
        ("node-fb-012", "Mulund High-Rise Cluster",        "highrise", 19.175, 72.956, 18, 750),
        ("node-fb-013", "Borivali National Park Shelter",  "school",   19.228, 72.856,  1, 350),
        ("node-fb-014", "Sion Hospital Zone",              "hospital", 19.039, 72.860,  4, 310),
        ("node-fb-015", "Navi Mumbai Sector 17 Tower",     "highrise", 19.022, 73.020, 24, 820),
    ]
    features = []
    for uid, name, cat, lat, lon, levels, cap in nodes:
        meta = CATEGORY_META[cat]
        elev = round(BASE_TERRAIN_ELEVATION_M + levels * FLOOR_HEIGHT_M, 1)
        features.append({
            "type": "Feature",
            "geometry": {"type": "Point", "coordinates": [lon, lat]},
            "properties": {
                "id": uid, "name": name, "category": cat,
                "label": meta["label"], "elevation_asl_m": elev,
                "capacity": cap, "status": meta["status"],
                "levels": str(levels), "osm_id": 0,
            },
        })
    return {"type": "FeatureCollection", "features": features}


def main():
    log.info("=== SENTINEL V7: OSM Evacuation Node Ingestion Pipeline ===")

    # If Parquet already exists and is recent (< 24 h), skip re-download
    if PARQUET_OUT.exists():
        age_h = (time.time() - PARQUET_OUT.stat().st_mtime) / 3600
        if age_h < 24:
            log.info(f"Parquet cache fresh ({age_h:.1f}h old) — skipping re-download.")
            return

    try:
        query    = build_overpass_query(BBOX)
        raw      = query_overpass(query)
        geojson  = build_geojson(raw.get("elements", []))
        if not geojson["features"]:
            raise ValueError("Empty feature set from Overpass — activating fallback.")
    except Exception as exc:
        log.error(f"Overpass pipeline error: {exc}")
        geojson = generate_fallback_nodes()

    save_geojson(geojson, GEOJSON_OUT)
    save_parquet(geojson, PARQUET_OUT)
    log.info("=== Pipeline complete. Evacuation dataset ready. ===")


if __name__ == "__main__":
    main()
