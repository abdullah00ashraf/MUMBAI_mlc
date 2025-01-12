````carousel
## File: `01_init_mumbai_grid.py`

**Key Functions:**
`assign_id`

**Size:** 2073 bytes
<!-- slide -->
## File: `02_extract_static_billion_grid.py`

**Size:** 2317 bytes
<!-- slide -->
## File: `03_fetch_weather_data.py`

**Size:** 2633 bytes
<!-- slide -->
## File: `03b_extract_weather.py`

**Key Functions:**
`fix_and_merge_encapsulated_nc_files`

**Size:** 2987 bytes
<!-- slide -->
## File: `04_tide_harmonic_engine.py`

**Classes:**
`TideHarmonicEngine`

**Key Functions:**
`__init__`, `authenticate_physics`, `calculate_instant`, `generate_2_decade_minute_archive`

**Size:** 3560 bytes
<!-- slide -->
## File: `05_extract_flood_target.py`

**Size:** 2137 bytes
<!-- slide -->
## File: `06_build_master_grid.py`

**Size:** 3142 bytes
<!-- slide -->
## File: `07_final_fusion.py`

**Key Functions:**
`run_fusion`

**Size:** 6140 bytes
<!-- slide -->
## File: `08_live_telemetry_daemon.py`

**Key Functions:**
`write_sync`

**Size:** 4628 bytes
<!-- slide -->
## File: `aegis_auditor\core\exceptions.py`

**Classes:**
`AEGISBaseException`, `SuiteError`, `RequestForInformation`, `HardwareAnomaly`, `TransitContradiction`, `HistoricalIgnorance`

**Key Functions:**
`__init__`, `__init__`, `__init__`, `__init__`, `__init__`

**Size:** 2061 bytes
<!-- slide -->
## File: `aegis_auditor\core\ingestion_engine.py`

**Size:** 6037 bytes
<!-- slide -->
## File: `aegis_auditor\core\physics_ground_truth.py`

**Classes:**
`L_Physics`

**Key Functions:**
`validate_mass_balance`, `get_runoff_coefficient`

**Size:** 1753 bytes
<!-- slide -->
## File: `aegis_auditor\db\ingestion_engine.py`

**Classes:**
`IngestionEngine`

**Key Functions:**
`__init__`, `parameter_mapping`

**Size:** 1887 bytes
<!-- slide -->
## File: `aegis_auditor\db\mongo_store.py`

**Classes:**
`AEGISMongoStore`

**Key Functions:**
`__init__`

**Size:** 3085 bytes
<!-- slide -->
## File: `aegis_auditor\judge_overseer.py`

**Classes:**
`JudgeOverseer`

**Key Functions:**
`__init__`

**Size:** 4814 bytes
<!-- slide -->
## File: `aegis_auditor\suites\s1_interrogator.py`

**Classes:**
`S1_Interrogator`

**Size:** 996 bytes
<!-- slide -->
## File: `aegis_auditor\suites\s2_watchdog.py`

**Classes:**
`TelemetryListener`, `S2_Watchdog`

**Key Functions:**
`__init__`, `__init__`

**Size:** 4527 bytes
<!-- slide -->
## File: `aegis_auditor\suites\s3_analyst.py`

**Classes:**
`S3_Analyst`

**Size:** 597 bytes
<!-- slide -->
## File: `aegis_auditor\suites\s4_predictor.py`

**Classes:**
`S4_Predictor`

**Key Functions:**
`__init__`

**Size:** 2384 bytes
<!-- slide -->
## File: `aegis_auditor\suites\s5_historian.py`

**Classes:**
`S5_Historian`

**Key Functions:**
`__init__`

**Size:** 2620 bytes
<!-- slide -->
## File: `aegis_auditor\suites\s6_telemetry.py`

**Classes:**
`S6_TelemetryAuditor`

**Size:** 883 bytes
<!-- slide -->
## File: `aegis_auditor\test_genesis_boot.py`

**Size:** 1289 bytes
<!-- slide -->
## File: `aegis_auditor\test_watchdog_bridge.py`

**Size:** 1759 bytes
<!-- slide -->
## File: `aegis_llm_auditor.py`

**Description/Title:**
> PROJECT SALSETTE: THE KONKAN-AEGIS PROTOCOL

**Key Functions:**
`execute_hardened_audit`

**Size:** 6276 bytes
<!-- slide -->
## File: `api\certify_sentinel.py`

**Classes:**
`SentinelCertifier`

**Key Functions:**
`_telemetry_base`, `__init__`, `generate_headers`, `generate_report`

**Size:** 7274 bytes
<!-- slide -->
## File: `api\coastal_db.py`

**Description/Title:**
> SQLite access for the Mumbai coastal vault — shared by FastAPI routes and tooling.

**Key Functions:**
`vault_db_path`, `_connect`, `ensure_schema`, `_row_to_dict`, `fetch_latest_telemetry_row`, `fetch_telemetry_stats`, `fetch_ward_summaries`, `insert_emergency_beacon`, `add_citizen_pin`, `fetch_citizen_pins`

**Size:** 6848 bytes
<!-- slide -->
## File: `api\dashboard_service.py`

**Description/Title:**
> Aggregated telemetry dashboard: DB + Open-Meteo + neural core + heuristics.

**Key Functions:**
`_heuristic_lock_frac`, `_neural_predict`, `_merge_rainfall`

**Size:** 9881 bytes
<!-- slide -->
## File: `api\latency_audit.py`

**Classes:**
`MockVault`, `MockRedis`

**Key Functions:**
`__init__`, `report`

**Size:** 3492 bytes
<!-- slide -->
## File: `api\main.py`

**Classes:**
`ConnectionManager`, `SentinelBiLSTM`, `TelemetryPayload`, `EmergencyLastKnown`, `CitizenPinPayload`

**Key Functions:**
`init_aegis_db`, `_cors_origins`, `_decrypt_model_blob`, `_division_risk_from_wards`, `__init__`, `disconnect`, `__init__`, `forward`

**Size:** 20286 bytes
<!-- slide -->
## File: `api\memory_utils.py`

**Classes:**
`SensitiveBuffer`

**Key Functions:**
`secure_zero`, `mlock`, `munlock`, `force_garbage_collection`, `__init__`, `__enter__`, `__exit__`

**Size:** 3305 bytes
<!-- slide -->
## File: `api\security_middleware.py`

**Classes:**
`PayloadIntegrityMiddleware`

**Key Functions:**
`_exempt_post_paths`

**Size:** 5352 bytes
<!-- slide -->
## File: `api\vault_manager.py`

**Classes:**
`VaultManager`

**Key Functions:**
`__init__`

**Size:** 3037 bytes
<!-- slide -->
## File: `check_files.py`

**Size:** 403 bytes
<!-- slide -->
## File: `field_survey_ops\topography_auditor.py`

**Size:** 0 bytes
<!-- slide -->
## File: `field_survey_ops\v4_field_calibrator.py`

**Classes:**
`SentinelDaemon`

**Key Functions:**
`__init__`, `_init_ledger`, `_load_state`, `_save_state`, `get_hardware_gps`, `fetch_digital_twin`, `update_geojson`, `write_observation`, `_daemon_loop`, `start_daemon`, `manual_override`

**Size:** 9240 bytes
<!-- slide -->
## File: `generate_report.py`

**Key Functions:**
`get_python_info`, `get_html_js_info`, `main`

**Size:** 3148 bytes
<!-- slide -->
## File: `neural_core_xray.py`

**Description/Title:**
> PROJECT SALSETTE: THE KONKAN-AEGIS PROTOCOL

**Key Functions:**
`crack_keras_core`

**Size:** 3497 bytes
<!-- slide -->
## File: `showcase\app.js`

**Key Functions:**
`runoff`, `openJsonModal`, `soilMoisture`, `fetchTelemetry`, `animate`, `closeDocumentModal`, `openDocumentModal`

**Size:** 26900 bytes
<!-- slide -->
## File: `showcase\chart_audit.html`

**Size:** 8713 bytes
<!-- slide -->
## File: `showcase\chart_convergence.html`

**Size:** 12328 bytes
<!-- slide -->
## File: `showcase\chart_paradox.html`

**Size:** 14495 bytes
<!-- slide -->
## File: `showcase\generate_charts.py`

**Size:** 6111 bytes
<!-- slide -->
## File: `showcase\index.html`

**Description/Title:**
> Project Salsette | The Konkan-Aegis Protocol

**Size:** 115154 bytes
<!-- slide -->
## File: `showcase\inject_charts.py`

**Size:** 2971 bytes
<!-- slide -->
## File: `showcase\style.css`

**Size:** 9121 bytes
<!-- slide -->
## File: `src\engine\athena_mumbai_nlp.py`

**Size:** 0 bytes
<!-- slide -->
## File: `src\engine\coastal_guardrails.py`

**Size:** 0 bytes
<!-- slide -->
## File: `src\engine\hybrid_train_pinn.py`

**Classes:**
`SentinelPhysicsModel`

**Key Functions:**
`get_dataset`, `run_colab_training`, `generator`, `__init__`, `call`, `train_step`

**Size:** 6231 bytes
<!-- slide -->
## File: `src\engine\train_mumbai_pinn.py`

**Classes:**
`MumbaiCoastalDataset`

**Key Functions:**
`initiate_neural_forge`, `__init__`, `__len__`, `__getitem__`

**Size:** 7011 bytes
<!-- slide -->
## File: `src\models\bi_lstm_mumbai_v1.py`

**Classes:**
`PINN_Loss`, `SentinelMumbaiPINN`

**Key Functions:**
`deploy_model`, `__init__`, `forward`, `__init__`, `forward`, `log_cosh_loss`

**Size:** 4723 bytes
<!-- slide -->
## File: `src\models\hydraulic_lock_generator.py`

**Key Functions:**
`generate_physics_informed_targets`

**Size:** 4318 bytes
<!-- slide -->
## File: `src\models\tidal_harmonic_sync.py`

**Key Functions:**
`generate_calibration_baseline`, `execute_harmonic_synthesis`

**Size:** 4966 bytes
<!-- slide -->
## File: `web\admin\expert.html`

**Description/Title:**
> Sentinel Mumbai · Analysis &amp; XAI

**Key Functions:**
`updateDynamicFooter`, `sx`, `downloadCSV`, `initExpertBackground`, `sy`, `animate`, `runSanityChecks`, `nx`, `filterTelemetry`, `generateSitRep`, `lat`, `lock`, `project`, `applyTaskSequence`, `refreshVisualFeedback`...

**Size:** 124224 bytes
<!-- slide -->
## File: `web\admin\index.html`

**Description/Title:**
> SENTINEL HUFP V7 | Mumbai Command

**Key Functions:**
`sx`, `initResourceMatrix`, `ndcX`, `pollBackend`, `sy`, `runBootSequence`, `fireSTARPulse`, `railRiskLabel`, `tickCountdown`, `fetchNASABackground`, `drawStarWave`, `populateSliders`, `renderGroup`, `fetchTelemetry`, `updateRailwayMonitor`...

**Size:** 132575 bytes
<!-- slide -->
## File: `web\admin\nala_manager.js`

**Key Functions:**
`triggerNalaAlert`, `updateSwarmHUD`, `getMetaContent`, `resolveApiRoot`, `findNearestNala`, `initSwarmIntelligence`, `syncSwarmWithBackend`, `fetchLiveNalaMesh`, `initializeSecureSession`, `sentinelBuildSignedHeaders`

**Size:** 6933 bytes
<!-- slide -->
## File: `web\admin\nala_worker.js`

**Key Functions:**
`processSwarm`, `initSwarm`

**Size:** 3046 bytes
<!-- slide -->
## File: `web\citizen\index.html`

**Description/Title:**
> SENTINEL HUFP V7 | Mumbai Public

**Key Functions:**
`updateCitizenRailway`, `sx`, `initCitizenSurvivalSuite`, `renderFaces`, `ndcX`, `sy`, `runBootSequence`, `radius`, `railRiskLabel`, `updateGlobalPins`, `fetchNASABackground`, `initCitizenRailway`, `fetchTelemetry`, `buildSignedHeaders`, `updateZones`...

**Size:** 166981 bytes
<!-- slide -->
## File: `web\citizen\intro.html`

**Description/Title:**
> SENTINEL V7 | Interactive Descent

**Key Functions:**
`createGasTexture`, `setupGlassShatter`, `startAutoPilot`, `init`, `createVolumetricNebula`, `setupScrollPhysics`, `onWindowResize`, `resizeTrailCanvas`, `resetIdleTimer`, `updateTrail`, `animate`, `progress`

**Size:** 17387 bytes
<!-- slide -->
## File: `web\citizen\sw.js`

**Size:** 738 bytes
<!-- slide -->
## File: `web\security\ml_kem_bridge.js`

**Size:** 3389 bytes
````
