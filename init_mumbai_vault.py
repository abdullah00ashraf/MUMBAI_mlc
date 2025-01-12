import sqlite3
import os

def initialize_mumbai_vault():
    db_path = 'HUFP_mumbai/data/mumbai_coastal_vault.db'
    
    # Ensure directory exists
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    print("[SYS] Initializing Mumbai Coastal Vault...")

    # Table 1: BMC Ward Topography (Static Spatial Data)
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS ward_topography (
        ward_id TEXT PRIMARY KEY,
        ward_name TEXT,
        avg_elevation_m REAL,
        impermeability_index REAL,
        drainage_capacity_m3_s REAL,
        distance_to_coast_m REAL
    )
    ''')

    # Table 2: Live & Historical Telemetry (Time-Series Data)
    # Indexed heavily for sub-50ms retrieval
    cursor.execute('''
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
    )
    ''')

    # Create a Composite B-Tree Index for rapid queries
    cursor.execute('''
    CREATE INDEX IF NOT EXISTS idx_time_ward ON telemetry_mesh(timestamp, ward_id)
    ''')

    # Emergency last-known positions (citizen portal offline failover)
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS emergency_last_known (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        lat REAL NOT NULL,
        lng REAL NOT NULL,
        status TEXT,
        client_note TEXT,
        received_at DATETIME DEFAULT CURRENT_TIMESTAMP
    )
    ''')

    conn.commit()
    conn.close()
    print("[OK] Mumbai Coastal Vault Architecture Locked.")
    print(f"[OK] Database located at: {db_path}")

if __name__ == "__main__":
    initialize_mumbai_vault()