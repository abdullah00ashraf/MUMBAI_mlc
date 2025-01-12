import cdsapi
import os
import time

# --- 1. SYSTEM INITIALIZATION ---
c = cdsapi.Client()
output_folder = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "raw", "weather")
os.makedirs(output_folder, exist_ok=True)

# Define the 14-Vector Weather Components[cite: 1, 2]
variables = [
    'total_precipitation',          # Essential for dH/dt calculation
    'volumetric_soil_water_layer_1', # Soil saturation for infiltration
    '10m_u_component_of_wind',      # For surge/momentum physics
    '10m_v_component_of_wind',      # For surge/momentum physics
    '2m_temperature',               # Surface energy balance
    'surface_pressure'              # Atmospheric pressure
]

# Spatial Bounds: Expanded to ensure 216k points are covered
# [North, West, South, East]
mumbai_bounds = [19.45, 72.65, 18.75, 73.20] 

years = [str(y) for y in range(2004, 2025)] # Up to 2024
months = ['06', '07', '08', '09']           # Peak Monsoon Window

print("🚀 Sentinel HUFP V7: Deep Weather Extraction Initialized.")
print(f"📍 Target Area: {mumbai_bounds}")

for year in years:
    output_path = os.path.join(output_folder, f"mumbai_monsoon_era5_{year}.nc")
    
    # Skip valid existing files to save API quota
    if os.path.exists(output_path) and os.path.getsize(output_path) > 1024 * 1000:
        print(f"⏭️ Skipping {year}: Valid file already exists.")
        continue

    print(f"\n⏳ Requesting {year} Monsoon (Rainfall + Soil + Physics Vectors)...")
    
    try:
        c.retrieve(
            'reanalysis-era5-single-levels',
            {
                'product_type': 'reanalysis',
                'format': 'netcdf',
                'variable': variables,
                'year': year,
                'month': months,
                'day': [f"{d:02d}" for d in range(1, 32)],
                'time': [f"{h:02d}:00" for h in range(24)],
                'area': mumbai_bounds,
            },
            output_path
        )
        
        # --- INTEGRITY CHECK ---
        file_size = os.path.getsize(output_path) / (1024 * 1024)
        if file_size < 2.0: # A full year monsoon should be > 2MB even for a small crop
            print(f"⚠️ Warning: {year} file size ({file_size:.2f} MB) is suspiciously small.")
        else:
            print(f"✅ {year} downloaded successfully ({file_size:.2f} MB).")
            
    except Exception as e:
        print(f"❌ Error downloading {year}: {e}")
        print("⏸️ Waiting 60 seconds before retry...")
        time.sleep(60)

print("\n🎉 ALL WEATHER DATA SECURED. Ready for Spatio-Temporal Fusion.")