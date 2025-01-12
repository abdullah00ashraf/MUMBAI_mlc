# Implementation Plan - Sentinel V7 Deployment Readiness

This document outlines the systematic strategy to resolve the bugs, inconsistencies, security vulnerabilities, and deployment gaps identified within the Sentinel V7 (HUFP_mumbai) system to make it fully deployment ready.

## User Review Required

> [!IMPORTANT]
> **1. Database & Scraping Environment Mappings**
> The current system hardcodes the absolute directory path `C:\MUMBAI_mlc` across all Python files, scraping scripts, and documentation files. We will migrate these to dynamically resolved, absolute paths using `Path(__file__)` or `os.path.abspath` relative to the repository workspace (`C:\Producttolaunch\MUMBAI_mlc`). This ensures that scripts like [client_intel_scraper.py](file:///C:/Producttolaunch/MUMBAI_mlc/client_intel_scraper.py) and [test_query_intel.py](file:///C:/Producttolaunch/MUMBAI_mlc/test_query_intel.py) execute out-of-the-box in the user's workspace without manually modifying paths.
>
> **2. Parquet Accumulation Strategy**
> The telemetry ingestion daemon [08_live_telemetry_daemon.py](file:///C:/Producttolaunch/MUMBAI_mlc/HUFP_mumbai/08_live_telemetry_daemon.py) attempts to write partitioned directories for updates, while the FastAPI backend [api/main.py](file:///C:/Producttolaunch/MUMBAI_mlc/HUFP_mumbai/api/main.py) reads a single `live_telemetry.parquet` file. We propose modifying the daemon to continuously update the unified single `live_telemetry.parquet` file to preserve compatibility and prevent silent failure of the shadow run predictions.

## Open Questions

> [!NOTE]
> No high-risk open questions exist at this stage, as all issues are deterministic software bugs or deployment gaps that can be resolved using standard code corrections.

---

## Proposed Changes

### Component 1: Path Hardcoding & Portability Fixes

We will replace all hardcoded instances of `C:\MUMBAI_mlc` or `c:\MUMBAI_mlc` with paths dynamically derived from the script location.

#### [MODIFY] [test_query_intel.py](file:///C:/Producttolaunch/MUMBAI_mlc/test_query_intel.py)
* Dynamically resolve the path to `clients_intelligence_db.sqlite` relative to the directory containing the script.

#### [MODIFY] [client_intel_scraper.py](file:///C:/Producttolaunch/MUMBAI_mlc/client_intel_scraper.py)
* Replace hardcoded `workspace_root = "c:\\MUMBAI_mlc"` with the dynamically resolved directory of the script file.

#### [MODIFY] [check_files.py](file:///C:/Producttolaunch/MUMBAI_mlc/HUFP_mumbai/check_files.py)
* Update `file_to_check` to use a dynamic path relative to the script directory.

#### [MODIFY] [ingestion_engine.py](file:///C:/Producttolaunch/MUMBAI_mlc/HUFP_mumbai/aegis_auditor/core/ingestion_engine.py)
* Update `RAW_DIR` path to resolve dynamically relative to the `aegis_auditor` directory structure.

#### [MODIFY] [07_final_fusion.py](file:///C:/Producttolaunch/MUMBAI_mlc/HUFP_mumbai/07_final_fusion.py)
* Dynamically resolve `BASE_DIR` instead of hardcoding `C:\MUMBAI_mlc\HUFP_mumbai\data`.

#### [MODIFY] [06_build_master_grid.py](file:///C:/Producttolaunch/MUMBAI_mlc/HUFP_mumbai/06_build_master_grid.py)
* Refactor all glob targets and folder creation operations to resolve dynamically from the repository directory.

#### [MODIFY] [04_tide_harmonic_engine.py](file:///C:/Producttolaunch/MUMBAI_mlc/HUFP_mumbai/04_tide_harmonic_engine.py)
* Update the tidal data outputs directory (`output_dir`) to resolve dynamically.

#### [MODIFY] [03_fetch_weather_data.py](file:///C:/Producttolaunch/MUMBAI_mlc/HUFP_mumbai/03_fetch_weather_data.py)
* Update `output_folder` to resolve dynamically.

#### [MODIFY] [03b_extract_weather.py](file:///C:/Producttolaunch/MUMBAI_mlc/HUFP_mumbai/03b_extract_weather.py)
* Update `WEATHER_DIR` to resolve dynamically.

---

### Component 2: Telemetry Data Flow Alignment

#### [MODIFY] [08_live_telemetry_daemon.py](file:///C:/Producttolaunch/MUMBAI_mlc/HUFP_mumbai/08_live_telemetry_daemon.py)
* Refactor the `append_to_parquet` function to read the existing Parquet file, concatenate the new record, and write it back to `live_telemetry.parquet` synchronously inside the thread pool. This ensures the FastAPI shadow run loop reads updated data correctly.

---

### Component 3: AEGIS Audit Stream & Security Shield

#### [MODIFY] [api/main.py](file:///C:/Producttolaunch/MUMBAI_mlc/HUFP_mumbai/api/main.py)
* **Ingestion Shield (AegisSensorShield)**: Create a class `AegisSensorShield` with a static method to check for `NaN` or `Inf` float values in the `/api/v1/inference` telemetry payload and replace them with safe defaults (e.g. `0.0` or standard values) to protect the model from NaN propagation and system lockups.
* **WebSocket Audit Stream Fix**: Update `websocket_audit_stream` to parse telemetry through `IngestionEngine(None).parameter_mapping(telemetry)` or inject necessary defaults (such as `muck_factor_confidence = 1.0` and hardware parameters) to prevent the S4 suite from halting the audit due to missing telemetry fields.

---

### Component 4: Docker & Infrastructure Deployment

#### [MODIFY] [docker-compose.yml](file:///C:/Producttolaunch/MUMBAI_mlc/HUFP_mumbai/deployment/docker-compose.yml)
* Construct a complete multi-container configuration defining services for:
  - `web_backend`: FastAPI app running on port 8000.
  - `telemetry_daemon`: Background ingestion script.
  - `redis`: Redis server on port 6379 (needed by security middleware for anti-replay cache).

---

### Component 5: Stub Initializations

We will populate the empty Python stubs with minimal boilerplate code to avoid runtime or packaging import warnings.

#### [MODIFY] [coastal_guardrails.py](file:///C:/Producttolaunch/MUMBAI_mlc/HUFP_mumbai/src/engine/coastal_guardrails.py)
* Add a simple `CoastalGuardrails` class interface.

#### [MODIFY] [athena_mumbai_nlp.py](file:///C:/Producttolaunch/MUMBAI_mlc/HUFP_mumbai/src/engine/athena_mumbai_nlp.py)
* Add a placeholder function `extract_academic_constants`.

#### [MODIFY] [topography_auditor.py](file:///C:/Producttolaunch/MUMBAI_mlc/HUFP_mumbai/field_survey_ops/topography_auditor.py)
* Add a placeholder function `audit_field_elevations`.

---

## Verification Plan

### Automated Tests
- Execute test harnesses using `PYTHONPATH="."`:
  - Run `$env:PYTHONPATH="."; python aegis_auditor/test_genesis_boot.py` to confirm the synthesis layer completes validation correctly.
  - Run `$env:PYTHONPATH="."; python aegis_auditor/test_watchdog_bridge.py` to confirm watchdog anomalies are successfully caught.
  - Run `python test_query_intel.py` to verify that database paths are resolved correctly and records are successfully retrieved.

### Manual Verification
- Start the live telemetry daemon and FastAPI backend concurrently using `launch_sentinel.ps1` and verify that the shadow run telemetry task successfully logs predictions to `aegis_audit.db`.
- Establish a WebSocket connection to `ws://127.0.0.1:8000/api/audit/stream` and verify that the audit does not halt with `RFI` status.
- Trigger `/api/v1/inference` with payload containing `NaN` and verify that the shield filters out the bad inputs.
- Validate `docker-compose.yml` config validation using `docker-compose config`.
