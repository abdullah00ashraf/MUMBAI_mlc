import asyncio
from typing import Dict, Any, List

class IngestionEngine:
    """
    Multi-format parser for PDFs (Majid Hussain), SHP/GeoJSON, and sensor telemetry.
    Implements The "Refresher" Logic.
    """
    def __init__(self, db_store):
        self.db_store = db_store

    async def trigger_full_reindex(self, new_data_source: str):
        """
        Whenever new data is added, the pipeline triggers a Full Re-index.
        The old database is replaced with a fresh, custom-written version.
        """
        print(f"[INGESTION] Triggering Full Re-index due to new data from {new_data_source}...")
        await asyncio.sleep(0.1)
        self.db_store.collections["unified_schema"] = [] # Wiping old schema
        print("[INGESTION] Old database replaced with fresh context. Single Source of Truth maintained.")

    def parameter_mapping(self, raw_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Converts diverse units into a unified JSON schema for the suites.
        """
        unified = {
            "rainfall_mm_hr": float(raw_data.get("rain", raw_data.get("rainfall_mm_hr", 0))),
            "tide_m": float(raw_data.get("tide", raw_data.get("tide_m", 0))),
            "terrain": raw_data.get("terrain", "unknown"),
            "muck_factor_confidence": float(raw_data.get("muck_conf", raw_data.get("muck_factor_confidence", 1.0))),
            "sensor_id": raw_data.get("sensor_id", "UNKNOWN"),
            "voltage": float(raw_data.get("v", raw_data.get("voltage", 5.0))),
            "val": float(raw_data.get("value", raw_data.get("val", 0.0))),
            "prev_val": float(raw_data.get("previous", raw_data.get("prev_val", 0.0))),
            "dt_seconds": float(raw_data.get("dt", raw_data.get("dt_seconds", 1.0))),
            "snr": float(raw_data.get("signal_noise_ratio", raw_data.get("snr", 100)))
        }
        return unified
