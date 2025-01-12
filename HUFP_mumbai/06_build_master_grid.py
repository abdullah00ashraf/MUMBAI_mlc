import os
import glob
import numpy as np
import pandas as pd
import rasterio
from rasterio.merge import merge

print("🧩 Phase 1: Stitching the 4 Ground Truth Tiles...")

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

# 1. Find the 4 target tiles
target_files = glob.glob(os.path.join(SCRIPT_DIR, "data", "raw", "target", "*.tif"))
if len(target_files) == 0:
    print("❌ Error: Could not find the target tiles. Make sure they are in data/raw/target/")
    exit()

# Open them and merge them
src_files_to_mosaic = [rasterio.open(fp) for fp in target_files]
mosaic, out_trans = merge(src_files_to_mosaic)
out_meta = src_files_to_mosaic[0].meta.copy()

# Save the master stitched image temporarily
out_meta.update({
    "driver": "GTiff", 
    "height": mosaic.shape[1], 
    "width": mosaic.shape[2], 
    "transform": out_trans
})

master_target_path = os.path.join(SCRIPT_DIR, "data", "raw", "target", "master_target_2017.tif")
with rasterio.open(master_target_path, "w", **out_meta) as dest:
    dest.write(mosaic)

# Close the open files
for src in src_files_to_mosaic: src.close()

print("🗺️ Phase 2: Generating the 100m Coordinate Grid...")

# 2. Extract coordinates for every pixel
with rasterio.open(master_target_path) as src:
    target_data = src.read(1)
    
    # Generate pixel indices and convert to coordinates
    rows, cols = np.indices(target_data.shape)
    xs, ys = rasterio.transform.xy(src.transform, rows.flatten(), cols.flatten())
    target_flat = target_data.flatten()

# Build the base DataFrame
df = pd.DataFrame({
    'longitude': xs, 
    'latitude': ys, 
    'is_flooded_2017': target_flat
})

print("⛰️ Phase 3: Piercing the Topography Layer (Elevation)...")

# 3. Sample the Elevation TIFF
elev_files = glob.glob(os.path.join(SCRIPT_DIR, "data", "raw", "elevation", "*.tif"))
with rasterio.open(elev_files[0]) as src:
    # We sample the elevation file at our exact target coordinates
    coords = zip(df['longitude'], df['latitude'])
    df['elevation_m'] = [val[0] for val in src.sample(coords)]

print("🏙️ Phase 4: Piercing the Urban Surface Layer (Concrete)...")

# 4. Sample the Landcover TIFF
land_files = glob.glob(os.path.join(SCRIPT_DIR, "data", "raw", "landcover", "*_Map.tif"))
with rasterio.open(land_files[0]) as src:
    coords = zip(df['longitude'], df['latitude'])
    df['landcover_class'] = [val[0] for val in src.sample(coords)]

print("🧹 Phase 5: Cleaning and Saving to Processed Data...")

# 5. Clean up the data
# Earth Engine sometimes exports 'null' ocean data as extremely low numbers.
# We will filter out any points where elevation is less than -50m (deep ocean).
df = df[df['elevation_m'] > -50].copy()

# Ensure the processed folder exists
os.makedirs(os.path.join(SCRIPT_DIR, "data", "processed"), exist_ok=True)
output_csv = os.path.join(SCRIPT_DIR, "data", "processed", "mumbai_static_master.csv")

# Save to CSV!
df.to_csv(output_csv, index=False)

print(f"\n✅ SUCCESS! Master Grid generated at: {output_csv}")
print(f"📊 Total Grid Cells Processed: {len(df):,}")
print("Take a look at the CSV file to see your Machine Learning dataset taking shape!")