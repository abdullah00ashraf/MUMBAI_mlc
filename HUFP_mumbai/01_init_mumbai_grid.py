import ee
import os
import json
import geopandas as gpd

# --- 1. INITIALIZE EARTH ENGINE ---
try:
    ee.Initialize(project='hufpsentinel001') 
    print("🌍 Earth Engine Initialized Successfully using project: hufpsentinel001.")
except Exception as e:
    print(f"❌ Initialization Failed. Error: {e}")
    exit()

# --- 2. DEFINE MUMBAI BOUNDING BOX ---
mumbai_bbox = ee.Geometry.Rectangle([72.75, 18.85, 73.10, 19.35])

# --- 3. CREATE THE 100x100m GRID ---
print("📐 Generating 100x100 meter Spatiotemporal Grid over Mumbai...")

grid_image = ee.Image.constant(1).clip(mumbai_bbox)

vectors = grid_image.reduceToVectors(
    geometry=mumbai_bbox,
    crs='EPSG:4326',
    scale=100,       
    geometryType='polygon',
    eightConnected=False,
    maxPixels=1e9
)

# --- 4. ASSIGN UNIQUE CELL IDs (FIXED CENTROID) ---
def assign_id(feature):
    # FIX: Added '1' as the maxError margin in meters
    centroid = feature.geometry().centroid(1) 
    lon = ee.Number(centroid.coordinates().get(0)).format('%.5f')
    lat = ee.Number(centroid.coordinates().get(1)).format('%.5f')
    cell_id = ee.String('cell_').cat(lat).cat('_').cat(lon)
    return feature.set('cell_id', cell_id)

mumbai_grid_with_ids = vectors.map(assign_id)

# --- 5. EXPORT AND SAVE LOCALLY ---
print("📥 Downloading Grid Coordinates to local machine (This may take 1-3 minutes)...")

try:
    grid_geojson = mumbai_grid_with_ids.getInfo()

    output_dir = os.path.dirname(os.path.abspath(__file__))
    geojson_path = os.path.join(output_dir, "mumbai_100m_grid.geojson")

    with open(geojson_path, 'w') as f:
        json.dump(grid_geojson, f)

    print(f"✅ Grid successfully saved to: {geojson_path}")

    # Verify count
    gdf = gpd.read_file(geojson_path)
    print(f"📊 Total Grid Cells Generated: {len(gdf)}")

except Exception as e:
    print(f"❌ Download Failed. Error: {e}")
    print("⚠️ If the error says 'Payload too large', GEE is blocking the direct download because the file is massive. Let me know!")