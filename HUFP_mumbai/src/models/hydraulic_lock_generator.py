import sqlite3
import pandas as pd
import numpy as np
import time
import os

# --- Configuration ---
DB_PATH = 'HUFP_mumbai/data/mumbai_coastal_vault.db'

# --- Physical Constants for Mumbai (BMC Estimates) ---
BASE_DRAINAGE_CAPACITY_MM_HR = 25.0  # Max rainfall the city can drain at low tide
TIDAL_LOCK_THRESHOLD_M = 3.0         # Tide level where drainage begins to fail
TOTAL_LOCK_ELEVATION_M = 4.5         # Tide level where gates close completely (0 drainage)
SEEPAGE_EVAPORATION_MM_HR = 2.0      # Natural ground absorption per hour

def generate_physics_informed_targets():
    print("=== INITIATING HYDRAULIC LOCK TARGET GENERATION ===")
    start_time = time.time()

    db_path_absolute = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../data/mumbai_coastal_vault.db'))
    if not os.path.exists(db_path_absolute):
        print(f"[ERR] Vault not found at {db_path_absolute}.")
        return

    conn = sqlite3.connect(db_path_absolute)
    
    # 1. Load the Vault into a Pandas DataFrame for vectorized math
    print("[SYS] Loading 31-year telemetry into memory...")
    query = "SELECT timestamp, ward_id, precip_mm_hr, tidal_height_m FROM telemetry_mesh ORDER BY ward_id, timestamp"
    df = pd.read_sql_query(query, conn)

    if df.empty:
        print("[ERR] Telemetry mesh is empty. Run ingestion scripts first.")
        return

    print(f"[OK] Loaded {len(df)} records. Processing physics equations...")

    # 2. Calculate Rolling 24-Hour Cumulative Rain (Fills the placeholder from Phase 1)
    # We group by ward_id just in case you add more wards later
    df['cumulative_rain_24h'] = df.groupby('ward_id')['precip_mm_hr'].transform(
        lambda x: x.rolling(window=24, min_periods=1).sum()
    )

    # 3. Calculate Tidal Multiplier (The Hydraulic Lock)
    # If tide < 3.0m -> Multiplier = 1.0 (100% drainage)
    # If tide > 4.5m -> Multiplier = 0.0 (0% drainage)
    # If between 3.0m and 4.5m -> Scales linearly down
    df['tidal_multiplier'] = np.clip(
        1.0 - ((df['tidal_height_m'] - TIDAL_LOCK_THRESHOLD_M) / (TOTAL_LOCK_ELEVATION_M - TIDAL_LOCK_THRESHOLD_M)),
        0.0, 
        1.0
    )

    df['effective_drainage_mm'] = (BASE_DRAINAGE_CAPACITY_MM_HR * df['tidal_multiplier']) + SEEPAGE_EVAPORATION_MM_HR

    # 4. Calculate Sequential Flood Accumulation
    # Because accumulation has a "floor" of 0 (water drains completely), 
    # we use an optimized Python loop rather than simple vectorized subtraction.
    print("[SYS] Simulating hour-by-hour urban accumulation...")
    
    precip_vals = df['precip_mm_hr'].values
    drainage_vals = df['effective_drainage_mm'].values
    
    flood_depths_mm = np.zeros(len(df))
    current_depth = 0.0
    
    for i in range(len(df)):
        current_depth += precip_vals[i]
        current_depth -= drainage_vals[i]
        if current_depth < 0:
            current_depth = 0.0
        flood_depths_mm[i] = current_depth

    # Convert millimeters to meters for our final database target
    df['actual_flood_depth_m'] = np.round(flood_depths_mm / 1000.0, 3)

    # 5. Bulk Commit to Database
    print("[SYS] Committing computed targets back to Vault...")
    cursor = conn.cursor()
    
    # Prepare update payload
    update_payload = list(zip(
        df['cumulative_rain_24h'].round(2).tolist(),
        df['actual_flood_depth_m'].tolist(),
        df['timestamp'].tolist(),
        df['ward_id'].tolist()
    ))

    # Execute in batches
    batch_size = 50000
    for i in range(0, len(update_payload), batch_size):
        batch = update_payload[i:i+batch_size]
        cursor.executemany('''
            UPDATE telemetry_mesh 
            SET cumulative_rain_24h = ?, actual_flood_depth_m = ?
            WHERE timestamp = ? AND ward_id = ?
        ''', batch)
        conn.commit()
        print(f"      -> Computed & committed batch {i} to {i+len(batch)}")

    conn.close()
    
    max_flood = df['actual_flood_depth_m'].max()
    print(f"=== PHYSICS ENGINE COMPLETE ===")
    print(f"Execution Time: {round(time.time() - start_time, 2)} seconds")
    print(f"Maximum Simulated Urban Depth: {max_flood} meters")

if __name__ == "__main__":
    generate_physics_informed_targets()