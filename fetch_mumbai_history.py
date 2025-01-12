import sqlite3
import pandas as pd
import requests
import time
from datetime import datetime
import os

# --- Configuration ---
DB_PATH = 'HUFP_mumbai/data/mumbai_coastal_vault.db'
# Mumbai Coordinates (Santacruz Observatory approximate)
LATITUDE = 19.08
LONGITUDE = 72.88
START_YEAR = 1993 # 31 years ago
END_YEAR = 2023   # End of last complete year

# --- Helper to chunk dates ---
def get_yearly_date_ranges(start_year, end_year):
    ranges = []
    for year in range(start_year, end_year + 1):
        ranges.append((f"{year}-01-01", f"{year}-12-31"))
    return ranges

# --- API Fetcher ---
def fetch_historical_weather(start_date, end_date):
    print(f"[SYS] Fetching data from {start_date} to {end_date}...")
    
    url = "https://archive-api.open-meteo.com/v1/archive"
    params = {
        "latitude": LATITUDE,
        "longitude": LONGITUDE,
        "start_date": start_date,
        "end_date": end_date,
        "hourly": "precipitation,temperature_2m,soil_moisture_0_to_7cm",
        "timezone": "Asia/Kolkata"
    }

    response = requests.get(url, params=params)
    
    if response.status_code == 200:
        return response.json()
    else:
        print(f"[ERR] Failed to fetch data for {start_date} to {end_date}. Status Code: {response.status_code}")
        print(f"[ERR] Response: {response.text}")
        return None

# --- Database Ingestion ---
def ingest_data_to_vault(data, cursor):
    if not data or 'hourly' not in data:
        return 0

    hourly = data['hourly']
    times = hourly['time']
    precip = hourly['precipitation']
    temp = hourly.get('temperature_2m', [None] * len(times)) # Safe get
    soil_moist = hourly.get('soil_moisture_0_to_7cm', [None] * len(times)) # Safe get

    records_inserted = 0
    # For now, we apply this general weather to all wards (or a central 'MUM_CENTRAL' ward)
    # Later, we can fetch specific coordinates for specific wards.
    default_ward = "MUM_CENTRAL"

    # Prepare data for bulk insert
    insert_data = []
    for i in range(len(times)):
        # Calculate a rolling 24h cumulative rain (simplified for insertion script, best done in Pandas before insert)
        # For this raw ingress, we just insert raw values. We calculate derived features later.
        
        # We handle None values gracefully
        p = precip[i] if precip[i] is not None else 0.0
        
        insert_data.append((
            times[i], 
            default_ward, 
            p, 
            0.0, # Placeholder for cumulative_24h, we will calculate this in a later pass
            0.0, # Placeholder for tide (we fetch this separately)
            None, # SAR_VH placeholder
            None  # Actual Flood Depth placeholder
        ))

    # We use INSERT OR IGNORE to prevent duplicate entries if the script is restarted
    cursor.executemany('''
        INSERT OR IGNORE INTO telemetry_mesh 
        (timestamp, ward_id, precip_mm_hr, cumulative_rain_24h, tidal_height_m, sar_vh_backscatter, actual_flood_depth_m)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    ''', insert_data)

    return len(times)

# --- Main Execution ---
def run_ingestion():
    # Ensure DB exists
    if not os.path.exists(DB_PATH):
        print(f"[ERR] Database not found at {DB_PATH}. Run initialization script first.")
        return

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Ensure a default ward exists to satisfy Foreign Key constraints
    cursor.execute('''
        INSERT OR IGNORE INTO ward_topography (ward_id, ward_name, avg_elevation_m, impermeability_index, drainage_capacity_m3_s, distance_to_coast_m)
        VALUES ('MUM_CENTRAL', 'Mumbai Central Observatory', 10.0, 0.95, 50.0, 2000.0)
    ''')
    conn.commit()

    date_ranges = get_yearly_date_ranges(START_YEAR, END_YEAR)
    total_records = 0

    print(f"=== Starting 31-Year Ingestion: {START_YEAR} to {END_YEAR} ===")
    
    for start, end in date_ranges:
        data = fetch_historical_weather(start, end)
        if data:
            records = ingest_data_to_vault(data, cursor)
            total_records += records
            conn.commit()
            print(f"[OK] Inserted {records} records for {start[:4]}.")
        
        # Be polite to the API
        time.sleep(1.5) 

    conn.close()
    print(f"=== Ingestion Complete. Total Hourly Records: {total_records} ===")

if __name__ == "__main__":
    # You may need to pip install requests pandas
    run_ingestion()