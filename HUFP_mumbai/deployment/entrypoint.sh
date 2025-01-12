#!/bin/bash

# Start the Zero-Latency Live Telemetry Ingestion Daemon in the background
echo "[SYS] Starting Live Telemetry Ingestion Daemon..."
python 08_live_telemetry_daemon.py &

# Start the FastAPI Backend on port 7860 (Hugging Face default port)
echo "[SYS] Launching FastAPI Backend on port 7860..."
exec uvicorn api.main:app --host 0.0.0.0 --port 7860
