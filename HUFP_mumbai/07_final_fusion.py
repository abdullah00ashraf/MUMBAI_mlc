import pandas as pd
import xarray as xr
import numpy as np
import os
import glob
import pyarrow as pa
import pyarrow.parquet as pq
from tqdm import tqdm
import gc

# --- 1. PATH CONFIGURATION ---
BASE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
STATIC_MASTER = os.path.join(BASE_DIR, "processed", "mumbai_static_master.csv")
WEATHER_DIR = os.path.join(BASE_DIR, "raw", "weather")
TIDE_DIR = os.path.join(BASE_DIR, "raw", "tide")
PARQUET_DIR = os.path.join(BASE_DIR, "processed", "fused_dataset")
os.makedirs(PARQUET_DIR, exist_ok=True)

# Process 24 hours (1 day) at a time to prevent RAM crashes
CHUNK_SIZE = 24 

def run_fusion():
    print("🧬 Loading Static Skeleton (216,284 Grid Cells)...")
    static_df = pd.read_csv(STATIC_MASTER)
    
    print("📐 Calculating Topographic Slope...")
    static_df['slope'] = np.arctan(static_df['elevation_m'].diff().fillna(0)).astype('float32')
    static_df['landcover_class'] = static_df['landcover_class'].astype('float32')

    nc_files = sorted(glob.glob(os.path.join(WEATHER_DIR, "*.nc")))
    
    for nc_path in nc_files:
        filename = os.path.basename(nc_path)
        year = filename.split('_')[-1].replace('.nc', '')
        
        output_file = os.path.join(PARQUET_DIR, f"mumbai_fusion_{year}.parquet")
        if os.path.exists(output_file):
            print(f"\n⏭️ Skipping {year} - Parquet file already exists.")
            continue
            
        print(f"\n🌦️ Fusing Weather & Tides for Year: {year}...")
        
        try:
            ds = xr.open_dataset(nc_path, engine='netcdf4')
            
            if 'valid_time' in ds.coords:
                ds = ds.rename({'valid_time': 'time'})
            elif 'valid_time' in ds.dims:
                ds = ds.rename_dims({'valid_time': 'time'})
                
            if 'tp' not in ds.variables:
                print(f"   ⚠️ WARNING: Year {year} is missing 'tp' (Rainfall). Skipping corrupted year.")
                continue
            
            tide_path = os.path.join(TIDE_DIR, f"mumbai_tide_1min_{year}.csv")
            if not os.path.exists(tide_path): 
                print(f"   ⚠️ Missing tide file for {year} ({tide_path}), skipping...")
                continue
            
            tide_df = pd.read_csv(tide_path)
            tide_df['timestamp'] = pd.to_datetime(tide_df['timestamp'])
            tide_df['tide_height_m'] = pd.to_numeric(tide_df['tide_height_m'], errors='coerce')
            tide_hourly = tide_df.set_index('timestamp').resample('h').mean(numeric_only=True).reset_index()

            monsoon_ds = ds.sel(time=ds.time.dt.month.isin([6, 7, 8, 9]))
            time_steps = monsoon_ds.time.values
            
            writer = None
            chunk_buffer = []
            
            for time_step in tqdm(time_steps, desc=f"Streaming {year} to Disk", unit="hr"):
                step_data = monsoon_ds.sel(time=time_step)
                temp_df = static_df.copy()
                
                ts_str = pd.to_datetime(time_step).strftime('%Y-%m-%d %H:%M:%S')
                temp_df['timestamp'] = ts_str
                
                temp_df['rainfall'] = step_data['tp'].sel(
                    longitude=xr.DataArray(static_df['longitude']),
                    latitude=xr.DataArray(static_df['latitude']),
                    method='nearest'
                ).values.astype('float32')
                
                temp_df['soil_moisture'] = step_data['swvl1'].sel(
                    longitude=xr.DataArray(static_df['longitude']),
                    latitude=xr.DataArray(static_df['latitude']),
                    method='nearest'
                ).values.astype('float32')

                current_tide = tide_hourly[tide_hourly['timestamp'] == time_step]['tide_height_m'].values
                temp_df['tide_height'] = current_tide[0] if len(current_tide) > 0 else 2.5
                
                cols = ['timestamp', 'longitude', 'latitude', 'rainfall', 'tide_height', 
                        'soil_moisture', 'elevation_m', 'slope', 'landcover_class', 'is_flooded_2017']
                
                if '2017' not in year:
                    temp_df['is_flooded_2017'] = 0 
                
                chunk_buffer.append(temp_df.reindex(columns=cols))
                
                # --- THE MEMORY SAVER: Write chunk and wipe RAM ---
                if len(chunk_buffer) >= CHUNK_SIZE:
                    chunk_df = pd.concat(chunk_buffer, ignore_index=True)
                    table = pa.Table.from_pandas(chunk_df)
                    
                    if writer is None:
                        # Initialize writer with the schema of the first chunk
                        writer = pq.ParquetWriter(output_file, table.schema, compression='snappy')
                        
                    writer.write_table(table)
                    
                    # Nuke the buffer from orbit to free RAM
                    del chunk_buffer
                    del chunk_df
                    del table
                    chunk_buffer = []
                    gc.collect()

            # --- Write any remaining hours at the end of the year ---
            if chunk_buffer:
                chunk_df = pd.concat(chunk_buffer, ignore_index=True)
                table = pa.Table.from_pandas(chunk_df)
                if writer is None:
                    writer = pq.ParquetWriter(output_file, table.schema, compression='snappy')
                writer.write_table(table)
                del chunk_buffer, chunk_df, table
                gc.collect()

            if writer:
                writer.close()
            
            ds.close()
            print(f"💾 Saved: {output_file} ({os.path.getsize(output_file) / (1024**2):.2f} MB)")

        except Exception as e:
            print(f"❌ Error in {year}: {e}")
            
    print("\n✅ ALL YEARS PROCESSED SECURELY VIA STREAMING.")

if __name__ == "__main__":
    run_fusion()