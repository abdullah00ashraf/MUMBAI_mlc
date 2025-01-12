import asyncio
import io
import json
import os
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
import uuid
import jwt

import torch
import torch.nn as nn
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from fastapi import FastAPI, HTTPException, Request, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
import sqlite3
import pandas as pd
import pyarrow.parquet as pq
import tensorflow as tf
from typing import List, Dict, Any, Optional
from pathlib import Path
import numpy as np
import sys
import importlib

_REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.append(str(_REPO_ROOT))

tide_harmonic_module = importlib.import_module("04_tide_harmonic_engine")
TideHarmonicEngine = tide_harmonic_module.TideHarmonicEngine

from api.security_middleware import redis_client
from aegis_auditor.db.ingestion_engine import IngestionEngine
from aegis_auditor.judge_overseer import JudgeOverseer
from fastapi.responses import JSONResponse

class DataImputationError(Exception):
    def __init__(self, parameter: str, reason: str):
        self.parameter = parameter
        self.reason = reason
        super().__init__(f"Data Imputation Failure for {parameter}: {reason}")

class AegisSensorShield:
    @staticmethod
    async def sanitize(payload: Dict[str, Any]) -> Dict[str, Any]:
        sanitized = {}
        target_time = datetime.now() # naive local time for tide calculation
        
        for k, v in payload.items():
            if v is None or (isinstance(v, float) and (np.isnan(v) or np.isinf(v))):
                # 1. Query Redis cache for Last Observation Carried Forward (LOCF)
                redis_key = f"sensor_locf:{k}"
                locf_val = None
                try:
                    locf_val = await redis_client.get(redis_key)
                except Exception as redis_err:
                    print(f"[SHIELD] Redis connection error during LOCF fetch: {redis_err}")
                
                if locf_val is not None:
                    try:
                        sanitized[k] = float(locf_val)
                        print(f"[SHIELD] LOCF applied for parameter '{k}': {sanitized[k]}")
                        continue
                    except:
                        pass
                
                # 2. Redis is cold/fails -> Fallback logic
                if k == "tidal_height":
                    try:
                        engine = TideHarmonicEngine()
                        tide_val = float(engine.calculate_instant(target_time))
                        sanitized[k] = tide_val
                        print(f"[SHIELD] Tide fallback to TideHarmonicEngine calculated tide: {tide_val}")
                    except Exception as tide_err:
                        raise DataImputationError(k, f"TideHarmonicEngine calculation failed: {tide_err}")
                else:
                    # For other missing or corrupt variables, raise DataImputationError
                    raise DataImputationError(k, f"Value is NaN/Inf and no LOCF cache exists in Redis.")
            else:
                sanitized[k] = v
                # Update Redis LOCF cache with the last known good value
                redis_key = f"sensor_locf:{k}"
                try:
                    await redis_client.set(redis_key, str(v))
                except Exception as redis_err:
                    pass
        return sanitized

from api.coastal_db import (
    ensure_schema,
    fetch_latest_telemetry_row,
    fetch_telemetry_stats,
    fetch_ward_summaries,
    insert_emergency_beacon,
    vault_db_path,
    add_citizen_pin,
    fetch_citizen_pins,
)
from api.dashboard_service import build_telemetry_dashboard
from api.memory_utils import force_garbage_collection, mlock, munlock, secure_zero
from api.security_middleware import PayloadIntegrityMiddleware
from api.vault_manager import vault

# --------------------------------------------------------------------------------
# SHADOW RUN BACKEND: WEBSOCKET & DB
# --------------------------------------------------------------------------------

class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)

    async def broadcast(self, message: dict):
        for connection in self.active_connections:
            try:
                await connection.send_json(message)
            except:
                pass

manager = ConnectionManager()

def init_aegis_db():
    conn = sqlite3.connect("aegis_audit.db")
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS shadow_audit
                 (timestamp TEXT, lat REAL, lon REAL, rain_mm REAL, tide_m REAL, lock_prob REAL)''')
    conn.commit()
    conn.close()

init_aegis_db()

# --------------------------------------------------------------------------------
# SENTINEL V7 - NEURAL CORE ARCHITECTURE
# --------------------------------------------------------------------------------

_REPO_ROOT = Path(__file__).resolve().parent.parent


class SentinelBiLSTM(nn.Module):
    def __init__(self, input_size=8, hidden_size=64, num_layers=2):
        super(SentinelBiLSTM, self).__init__()
        self.lstm = nn.LSTM(
            input_size, hidden_size, num_layers, batch_first=True, bidirectional=True
        )
        self.fc = nn.Linear(hidden_size * 2, 2)

    def forward(self, x):
        out, _ = self.lstm(x)
        return self.fc(out[:, -1, :])


sentinel_core = SentinelBiLSTM()


def _cors_origins() -> List[str]:
    raw = os.getenv(
        "SENTINEL_CORS_ORIGINS",
        "http://127.0.0.1:5500,http://localhost:5500,http://127.0.0.1:8000,http://localhost:8000,http://127.0.0.1:8080,http://localhost:8080,null",
    )
    return [o.strip() for o in raw.split(",") if o.strip()]


def _decrypt_model_blob(dek: bytes, encrypted_data: bytes) -> bytes:
    """
    Preferred on-disk layout: 12-byte nonce || ciphertext (AES-GCM tag appended by encryptor).
    Legacy: full blob decrypted with an all-zero nonce (single-artifact demo only).
    """
    aesgcm = AESGCM(dek)
    if len(encrypted_data) >= 12 + 16 + 1:
        nonce = encrypted_data[:12]
        ciphertext = encrypted_data[12:]
        try:
            return aesgcm.decrypt(nonce, ciphertext, None)
        except Exception:
            pass
    return aesgcm.decrypt(b"\x00" * 12, encrypted_data, None)


# --------------------------------------------------------------------------------
# PHASE 1: SECURE NEURAL IGNITION (LIFESPAN)
# --------------------------------------------------------------------------------


@asynccontextmanager
async def lifespan(app: FastAPI):
    print("\n[IGNITION] --- Sentinel V7: Initializing Secure Neural Ignition ---")
    app.state.neural_ready = False
    ensure_schema()
    print(f"[IGNITION] Coastal vault DB path: {vault_db_path()}")

    model_path = _REPO_ROOT / "models" / "sentinel_mumbai_v1_cloud.pt"
    if not model_path.is_file():
        model_path = Path("models/sentinel_mumbai_v1_cloud.pt")

    dek_raw = await vault.get_encryption_key()
    dek_buffer = bytearray(dek_raw)

    try:
        mlock(dek_buffer)
        if not model_path.is_file():
            print(f"[WARN] Model missing at {model_path}. Starting in SIMULATION mode.")
        else:
            with open(model_path, "rb") as f:
                encrypted_data = f.read()

            plaintext_bytes = _decrypt_model_blob(bytes(dek_buffer), encrypted_data)
            bytes_buffer = io.BytesIO(plaintext_bytes)

            state_dict = torch.load(bytes_buffer, weights_only=True)
            sentinel_core.load_state_dict(state_dict)
            sentinel_core.eval()

            secure_zero(bytearray(plaintext_bytes))
            bytes_buffer.close()
            app.state.neural_ready = True
            print("[SUCCESS] Neural Core Seated inside Armored Perimeter.")

    except Exception as e:
        print(f"[CRITICAL] IGNITION FAILURE: {e}")
    finally:
        secure_zero(dek_buffer)
        munlock(dek_buffer)
        force_garbage_collection()
        print("[CLEANUP] Cryptographic DEK annihilated from RAM.\n")

    # Load Keras Model for Shadow Run
    keras_path = _REPO_ROOT / "v7_latest_brain.keras"
    if keras_path.is_file():
        app.state.keras_model = tf.keras.models.load_model(keras_path)
        print("[IGNITION] Keras Shadow Run Model loaded.")
    else:
        app.state.keras_model = None
        print("[WARN] Keras model missing. Shadow Run will simulate probabilities.")

    async def shadow_run_telemetry_task(app_ref):
        print("[SHADOW RUN] Background ingestion task started.")
        while True:
            try:
                parquet_file = _REPO_ROOT / "data" / "live_telemetry.parquet"
                if parquet_file.exists():
                    table = pq.read_table(parquet_file)
                    df = table.to_pandas()
                    latest = df.iloc[-1]
                    
                    if getattr(app_ref.state, 'keras_model', None) is not None:
                        input_vector = [latest['rain_mm'], latest['tide_m'], 0.0, 0.0, 80.0, 0.5, 10.0, 1013.2]
                        input_tensor = np.array([input_vector], dtype=np.float32)
                        pred = app_ref.state.keras_model.predict(input_tensor, verbose=0)
                        lock_prob = float(pred[0][1]) if pred.shape[1] > 1 else float(pred[0][0])
                    else:
                        # Fallback heuristic if Keras model is missing
                        lock_prob = min(0.99, (latest['rain_mm'] * 0.05) + (latest['tide_m'] * 0.1))

                    conn = sqlite3.connect("aegis_audit.db")
                    c = conn.cursor()
                    c.execute("INSERT INTO shadow_audit VALUES (?, ?, ?, ?, ?, ?)", 
                              (latest['timestamp'], latest['lat'], latest['lon'], latest['rain_mm'], latest['tide_m'], lock_prob))
                    conn.commit()
                    conn.close()

                    await manager.broadcast({
                        "timestamp": latest['timestamp'],
                        "hydraulic_lock_probability": lock_prob,
                        "rain_mm": float(latest['rain_mm']),
                        "tide_m": float(latest['tide_m'])
                    })
            except Exception as e:
                print(f"[SHADOW RUN] Error: {e}")
            await asyncio.sleep(300)

    bg_task = asyncio.create_task(shadow_run_telemetry_task(app))
    yield
    bg_task.cancel()
    print("--- Sentinel V7 Core Shutdown ---")


# --------------------------------------------------------------------------------
# API INITIALIZATION & SECURITY SHIELD
# --------------------------------------------------------------------------------

app = FastAPI(title="Sentinel V7 Mumbai Admin Core", lifespan=lifespan)

@app.exception_handler(DataImputationError)
async def data_imputation_exception_handler(request: Request, exc: DataImputationError):
    try:
        conn = sqlite3.connect("aegis_audit.db")
        c = conn.cursor()
        c.execute('''CREATE TABLE IF NOT EXISTS imputation_errors
                     (timestamp TEXT, parameter TEXT, reason TEXT)''')
        c.execute("INSERT INTO imputation_errors VALUES (?, ?, ?)",
                  (datetime.now(timezone.utc).isoformat(), exc.parameter, exc.reason))
        conn.commit()
        conn.close()
    except Exception as log_err:
        print(f"[ERROR] Failed to log imputation error: {log_err}")

    return JSONResponse(
        status_code=422,
        content={"detail": [{"loc": ["body", exc.parameter], "msg": str(exc), "type": "value_error.imputation"}]}
    )

app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins(),
    allow_origin_regex=".*",
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
    expose_headers=["X-Signature", "X-Timestamp", "X-Nonce"],
)

app.add_middleware(PayloadIntegrityMiddleware)


# --------------------------------------------------------------------------------
# INFERENCE & ANALYTICS ROUTES
# --------------------------------------------------------------------------------


class TelemetryPayload(BaseModel):
    rainfall: float = Field(..., description="Rainfall (mm/h)")
    tidal_height: float = Field(..., description="Tide (m)")
    flow_a: float = Field(..., description="Nala Flow Rate Sector A")
    flow_b: float = Field(..., description="Nala Flow Rate Sector B")
    humidity: float = Field(default=80.0)
    soil_moisture: float = Field(default=0.5)
    wind_speed: float = Field(default=10.0)
    pressure: float = Field(default=1013.2)


class EmergencyLastKnown(BaseModel):
    lat: float
    lng: float
    status: Optional[str] = None
    client_note: Optional[str] = None


def _division_risk_from_wards(wards: List[Dict[str, Any]]) -> float:
    if not wards:
        return 24.5
    risks: List[float] = []
    for w in wards:
        p = w.get("precip_mm_hr") or 0.0
        f = w.get("actual_flood_depth_m")
        f = f if f is not None else 0.0
        risks.append(min(100.0, float(p) * 2.0 + float(f) * 40.0))
    return sum(risks) / len(risks)


@app.post("/api/v1/inference")
async def perform_inference(payload: TelemetryPayload):
    try:
        # Sanitize incoming payload via AegisSensorShield
        raw_payload = payload.dict()
        sanitized = await AegisSensorShield.sanitize(raw_payload)

        input_vector = [
            sanitized["rainfall"],
            sanitized["tidal_height"],
            sanitized["flow_a"],
            sanitized["flow_b"],
            sanitized["humidity"],
            sanitized["soil_moisture"],
            sanitized["wind_speed"],
            sanitized["pressure"],
        ]
        input_tensor = torch.tensor([input_vector], dtype=torch.float32).unsqueeze(1)

        with torch.no_grad():
            prediction = sentinel_core(input_tensor)

        flood_depth = float(prediction[0][0])
        lock_prob = float(prediction[0][1])
        flood_depth_m = round(max(0, flood_depth), 3)
        lock_pct = round(max(0, min(1, lock_prob)) * 100, 2)

        uncertainty_flag = sanitized["rainfall"] > 100.0
        choke_alert = (
            sanitized["flow_a"] < 0.05
            and sanitized["flow_b"] < 0.05
            and sanitized["rainfall"] > 25.0
        )
        event_tag = ""
        if sanitized["tidal_height"] > 2.5 and sanitized["rainfall"] > 15.0:
            event_tag = "Oceanic"

        return {
            "status": "CRITICAL_BLOCKAGE" if flood_depth_m > 1.5 else "NOMINAL",
            "inference": {
                "flood_depth_m": flood_depth_m,
                "lock_probability": lock_pct,
            },
            "uncertainty_flag": uncertainty_flag,
            "choke_alert": choke_alert,
            "event_tag": event_tag,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    except DataImputationError as die:
        # Re-raise DataImputationError so the exception handler catches it and returns 422
        raise die
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Inference Failure: {str(e)}")


@app.get("/api/v1/telemetry/dashboard")
async def get_telemetry_dashboard(request: Request):
    """
    Full tactical payload for citizen/admin: DB + Open-Meteo + neural/heuristic lock,
    plus hydrology_tensor, xai, pumps, nodes, sitreps.
    """
    neural_ready = bool(getattr(request.app.state, "neural_ready", False))
    db_row = await asyncio.to_thread(fetch_latest_telemetry_row)
    return await build_telemetry_dashboard(
        sentinel_core,
        neural_ready=neural_ready,
        db_row=db_row,
    )


@app.get("/api/v1/telemetry/live")
async def get_live_telemetry():
    row = await asyncio.to_thread(fetch_latest_telemetry_row)
    if row:
        precip = float(row.get("precip_mm_hr") or 0.0)
        tide = float(row.get("tidal_height_m") or 0.0)
        flood = row.get("actual_flood_depth_m")
        lock_guess = min(99.0, precip * 1.5 + (float(flood) if flood is not None else 0.0) * 20.0)
        return {
            "hydraulic_lock_probability": round(lock_guess / 100.0, 4),
            "rainfall_intensity": round(precip, 2),
            "tidal_height_m": round(tide, 3),
            "ward_id": row.get("ward_id"),
            "observed_flood_depth_m": flood,
            "status": "ELEVATED" if lock_guess > 45 else "NOMINAL",
            "source": "mumbai_coastal_vault",
            "timestamp": row.get("timestamp"),
        }
    return {
        "hydraulic_lock_probability": 0.35,
        "rainfall_intensity": 12.4,
        "status": "NOMINAL",
        "source": "default_stub",
    }


@app.get("/api/v1/analytics/realtime")
async def get_realtime_analytics():
    stats = await asyncio.to_thread(fetch_telemetry_stats)
    wards = await asyncio.to_thread(fetch_ward_summaries)
    if stats["count"] == 0:
        return {
            "average_division_risk": 24.5,
            "total_indexed_records": 0,
            "current_discharge": 32.4,
            "status": "HEALTHY",
            "source": "default_stub",
        }
    avg_risk = _division_risk_from_wards(wards)
    discharge = sum(float(w.get("drainage_capacity_m3_s") or 0.0) for w in wards)
    if discharge <= 0:
        discharge = 32.4
    return {
        "average_division_risk": round(avg_risk, 2),
        "total_indexed_records": stats["count"],
        "current_discharge": round(discharge, 2),
        "status": "HEALTHY",
        "source": "mumbai_coastal_vault",
        "latest_timestamp": stats["latest_ts"],
    }


@app.get("/api/v1/analytics/division-summary")
async def get_division_summary():
    """Expert console: same payload shape as legacy /analytics/division-summary."""
    stats = await asyncio.to_thread(fetch_telemetry_stats)
    wards = await asyncio.to_thread(fetch_ward_summaries)
    avg_risk = _division_risk_from_wards(wards)
    discharge = sum(float(w.get("drainage_capacity_m3_s") or 0.0) for w in wards)
    if discharge <= 0:
        discharge = 32.4

    sar_vals = [w.get("sar_vh_backscatter") for w in wards if w.get("sar_vh_backscatter") is not None]
    sar_vh = sum(sar_vals) / len(sar_vals) if sar_vals else None

    n = min(24, max(4, (stats["count"] % 25) + 4)) if stats["count"] else 0
    loss_hist = (
        [round(max(0.1, avg_risk * (1.0 - i * 0.03)), 2) for i in range(n)]
        if stats["count"]
        else []
    )
    sar_hist = (
        [round((sar_vh or 0) * (0.92 + 0.01 * (i % 5)), 3) for i in range(min(12, n or 4))]
        if stats["count"]
        else []
    )

    return {
        "average_division_risk": round(avg_risk, 2),
        "avg_risk": round(avg_risk, 2),
        "total_indexed_records": stats["count"],
        "totalRecords": stats["count"],
        "current_discharge": round(discharge, 2),
        "currentDischarge": round(discharge, 2),
        "status": "HEALTHY",
        "sar_vh": sar_vh,
        "loss_mae": round(avg_risk / 200.0, 5) if stats["count"] else None,
        "loss_history": loss_hist,
        "sar_history": sar_hist,
        "bayesian_uncertainty": round(min(99.0, avg_risk * 0.15), 3) if stats["count"] else None,
        "aleatoric_noise": round(min(50.0, avg_risk * 0.25), 2) if stats["count"] else None,
        "basin_yield": round(min(100.0, avg_risk * 0.9), 1) if stats["count"] else None,
        "grid_state": f"{len(wards)} wards indexed" if wards else "no ward topography loaded",
        "source": "mumbai_coastal_vault",
        "latest_timestamp": stats["latest_ts"],
    }


@app.get("/api/v1/hydrology/current")
async def get_current_hydrology():
    row = await asyncio.to_thread(fetch_latest_telemetry_row)
    if row:
        return {
            "currentPrecip": float(row.get("precip_mm_hr") or 0.0),
            "soilMoisture": 0.45,
            "waterLevel": float(row.get("tidal_height_m") or 1.2),
            "ward_id": row.get("ward_id"),
            "source": "mumbai_coastal_vault",
            "timestamp": row.get("timestamp"),
        }
    return {
        "currentPrecip": 12.4,
        "soilMoisture": 0.45,
        "waterLevel": 1.2,
        "source": "default_stub",
    }


@app.post("/api/v1/emergency/last-known")
async def post_emergency_last_known(payload: EmergencyLastKnown):
    note = payload.client_note or payload.status
    row_id = await asyncio.to_thread(
        insert_emergency_beacon,
        payload.lat,
        payload.lng,
        payload.status,
        note,
    )
    return {
        "status": "BUFFERED",
        "record_id": row_id,
        "received_at": datetime.now(timezone.utc).isoformat(),
    }


class CitizenPinPayload(BaseModel):
    lat: float
    lng: float
    condition: str
    timestamp: Optional[str] = None


@app.post("/api/v1/emergency/citizen-pin")
async def post_citizen_pin(payload: CitizenPinPayload):
    row_id = await asyncio.to_thread(
        add_citizen_pin,
        payload.lat,
        payload.lng,
        payload.condition,
    )
    return {
        "status": "PIN_DROPPED",
        "record_id": row_id,
        "received_at": datetime.now(timezone.utc).isoformat(),
    }


@app.get("/api/v1/emergency/citizen-pins")
async def get_citizen_pins():
    pins = await asyncio.to_thread(fetch_citizen_pins)
    return {"pins": pins}


@app.post("/api/v1/telemetry/swarm_aggregation")
async def aggregate_swarm_data(request: Request):
    raw = await request.body()
    try:
        body = json.loads(raw.decode("utf-8")) if raw else {}
    except json.JSONDecodeError:
        body = {}
    nodes = body.get("active_nodes") or body.get("totalNodes")
    if nodes is None:
        nodes = 100000
    return {
        "status": "SYNCED",
        "active_nodes": nodes,
        "cluster_health": "OPTIMAL",
        "processed_at": datetime.now(timezone.utc).isoformat(),
        "echo_keys": list(body.keys())[:12] if isinstance(body, dict) else [],
    }



# --------------------------------------------------------------------------------
# PHASE 4: AUTHENTICATION & SESSION MANAGEMENT
# --------------------------------------------------------------------------------

@app.get("/api/v1/auth/session")
async def create_secure_session():
    """
    Issues a short-lived JWT session token for the Sentinel HUD.
    """
    secret = await vault.get_hmac_secret()
    payload = {
        "iat": datetime.now(timezone.utc),
        "exp": datetime.now(timezone.utc) + timedelta(hours=1),
        "session_id": str(uuid.uuid4())
    }
    token = jwt.encode(payload, secret, algorithm="HS256")
    return {"token": token}

@app.websocket("/ws/telemetry")
async def websocket_telemetry(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            # Keep connection alive
            data = await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket)

aegis_judge = JudgeOverseer()

@app.websocket("/api/audit/stream")
async def websocket_audit_stream(websocket: WebSocket):
    await websocket.accept()
    try:
        while True:
            # Fetch latest telemetry to feed to the auditor
            row = await asyncio.to_thread(fetch_latest_telemetry_row)
            telemetry = {}
            if row:
                telemetry = {
                    "rainfall_mm_hr": float(row.get("precip_mm_hr") or 0.0),
                    "tide_m": float(row.get("tidal_height_m") or 0.0),
                    "terrain": "urban_concrete"
                }
            
            # Map parameters using IngestionEngine parser to ensure all required fields for the suites are populated
            parser = IngestionEngine(None)
            mapped_telemetry = parser.parameter_mapping(telemetry)
            
            result = await aegis_judge.execute_audit(mapped_telemetry)
            await websocket.send_json({"audit_cycle": "ACTIVE", "telemetry_in": mapped_telemetry, "synthesis": result})
            await asyncio.sleep(8)
    except WebSocketDisconnect:
        print("[AEGIS] Client disconnected from audit stream")


# --------------------------------------------------------------------------------
# PHASE 5: EVACUATION ROUTING — NODE CATALOGUE
# --------------------------------------------------------------------------------

_EVAC_PARQUET = _REPO_ROOT / "data" / "evacuation_nodes.parquet"
_EVAC_GEOJSON = _REPO_ROOT / "data" / "evacuation_nodes.geojson"

def _load_evacuation_nodes() -> dict:
    """Load evacuation nodes from Parquet (preferred) or raw GeoJSON fallback."""
    if _EVAC_PARQUET.exists():
        df = pd.read_parquet(_EVAC_PARQUET)
        features = []
        for _, row in df.iterrows():
            features.append({
                "type": "Feature",
                "geometry": {"type": "Point", "coordinates": [float(row["lon"]), float(row["lat"])]},
                "properties": {
                    "id"              : str(row["id"]),
                    "name"            : str(row["name"]),
                    "category"        : str(row["category"]),
                    "label"           : str(row["label"]),
                    "elevation_asl_m" : float(row["elevation_asl_m"]),
                    "capacity"        : int(row["capacity"]),
                    "status"          : str(row["status"]),
                    "levels"          : str(row["levels"]),
                    "osm_id"          : int(row["osm_id"]),
                },
            })
        return {"type": "FeatureCollection", "features": features}

    if _EVAC_GEOJSON.exists():
        import json as _json
        with open(_EVAC_GEOJSON, "r", encoding="utf-8") as f:
            return _json.load(f)

    # Inline minimal fallback so the API never returns 500
    return {"type": "FeatureCollection", "features": [], "note": "Run 09_osm_evacuation_ingester.py to populate dataset."}


@app.get("/api/v1/evacuation/nodes")
async def get_evacuation_nodes():
    """
    Returns all verified Greater Mumbai evacuation nodes as a GeoJSON
    FeatureCollection (high-rises, schools, hospitals, police stations).
    Designed for direct Turf.js spatial indexing on the client side.
    """
    try:
        geojson = await asyncio.to_thread(_load_evacuation_nodes)
        return geojson
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Evacuation node load failure: {exc}")


class WaveSimulationInput(BaseModel):
    mangrove_density: float = Field(..., ge=0, le=100)
    tide_height: float = Field(..., ge=0)
    rainfall_rate: float = Field(..., ge=0)


@app.post("/api/v1/simulation/wave-attenuation")
async def simulate_wave_attenuation(payload: WaveSimulationInput):
    """
    PINN wave damping and coastal inundation simulation backend endpoint.
    Enforces a single source of truth for physics calculations.
    """
    try:
        from src.engine.coastal_guardrails import CoastalGuardrails
        cg = CoastalGuardrails()
        results = cg.simulate_wave_damping(
            mangrove_density_pct=payload.mangrove_density,
            rainfall_mm_hr=payload.rainfall_rate,
            tide_height_m=payload.tide_height
        )
        return results
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Simulation failed: {e}")


class CitizenReportInput(BaseModel):
    incident_type: str
    water_level_ft: float
    latitude: float
    longitude: float
    timestamp: str


@app.post("/api/v1/telemetry/citizen-report")
async def citizen_report_telemetry(payload: CitizenReportInput, request: Request):
    """
    Ingests crowdsourced reports signed with an anonymous HMAC signature.
    """
    device_key_id = request.headers.get("X-Device-Key-Id")
    ts = request.headers.get("X-Timestamp")
    nonce = request.headers.get("X-Nonce")
    signature = request.headers.get("X-HMAC-Signature")

    try:
        conn = sqlite3.connect("aegis_audit.db")
        c = conn.cursor()
        c.execute('''CREATE TABLE IF NOT EXISTS citizen_reports
                     (timestamp TEXT, device_key_id TEXT, incident_type TEXT, water_level_ft REAL, latitude REAL, longitude REAL, verified INTEGER)''')
        
        # Determine verified status based on HMAC existence
        verified = 1 if (signature and device_key_id) else 0
        
        c.execute("INSERT INTO citizen_reports VALUES (?, ?, ?, ?, ?, ?, ?)",
                  (payload.timestamp, device_key_id, payload.incident_type, payload.water_level_ft, payload.latitude, payload.longitude, verified))
        conn.commit()
        conn.close()

        # Update the live citizen pin database cache
        try:
            add_citizen_pin(
                lat=payload.latitude,
                lon=payload.longitude,
                label=f"{payload.incident_type} ({payload.water_level_ft} ft)",
                category="hazard",
                capacity=0,
                elevation=0.0
            )
        except Exception as pin_err:
            print(f"[REPORT] Failed to add citizen pin to vault: {pin_err}")

        print(f"[REPORT] Received crowdsourced report from {device_key_id} (Verified: {verified})")
        return {"status": "SUCCESS", "verified": verified}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database logging failed: {e}")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)


