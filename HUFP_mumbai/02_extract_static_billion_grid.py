import ee
import time

# --- 1. INITIALIZE ---
try:
    ee.Initialize(project='hufpsentinel001')
    print("🌍 Earth Engine Initialized.")
except Exception as e:
    print(f"❌ Error: {e}")
    exit()

# --- 2. DIVIDE AND CONQUER: CREATE 4 QUADRANTS ---
min_lon, min_lat = 72.75, 18.85
max_lon, max_lat = 73.10, 19.35

mid_lon = (min_lon + max_lon) / 2.0
mid_lat = (min_lat + max_lat) / 2.0

quadrants = {
    "SW_Tile": ee.Geometry.Rectangle([min_lon, min_lat, mid_lon, mid_lat]),
    "SE_Tile": ee.Geometry.Rectangle([mid_lon, min_lat, max_lon, mid_lat]),
    "NW_Tile": ee.Geometry.Rectangle([min_lon, mid_lat, mid_lon, max_lat]),
    "NE_Tile": ee.Geometry.Rectangle([mid_lon, mid_lat, max_lon, max_lat])
}

print("🗺️ Assembling Advanced Static Layers...")

# --- 3. THE DATA LAYERS ---
lonlat = ee.Image.pixelLonLat()
elev = ee.ImageCollection("JAXA/ALOS/AW3D30/V4_1").select('DSM').mosaic()
slope = ee.Terrain.slope(elev)

# FIX: Added .unmask(0) so tiles without land don't instantly crash
water_mask = ee.ImageCollection("JAXA/ALOS/AW3D30/V4_1").select('MASK').mosaic().unmask(0).bitwiseAnd(1)
distance_to_water = water_mask.fastDistanceTransform().multiply(30)

built_up = ee.ImageCollection("GOOGLE/DYNAMICWORLD/V1") \
            .filterDate('2021-01-01', '2022-01-01') \
            .select('built') \
            .mean()

master_static = ee.Image.cat([
    lonlat, elev, slope, distance_to_water, built_up
]).rename([
    'longitude', 'latitude', 'elevation_m', 'slope_deg', 'dist_to_water_m', 'impervious_ratio'
])

# --- 4. LAUNCH PARALLEL EXPORTS ---
print("🚀 Launching 4 Tiled GeoTIFF Exports to Google Drive...")

for tile_name, tile_geom in quadrants.items():
    print(f"Submitting task for: {tile_name}")
    
    task = ee.batch.Export.image.toDrive(
        image=master_static.clip(tile_geom),
        description=f'Sentinel_V7_Static_{tile_name}',
        folder='HUFP_Sentinel_Billion_Data',
        fileNamePrefix=f'mumbai_static_{tile_name}_100m',
        region=tile_geom,
        scale=100,
        crs='EPSG:4326',
        maxPixels=1e13,
        fileFormat='GeoTIFF'
    )
    task.start()

print("\n✅ All 4 Quadrant Tasks submitted!")
print("👀 Monitor here: https://code.earthengine.google.com/tasks")