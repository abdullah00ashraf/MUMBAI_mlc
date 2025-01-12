import ee

try:
    ee.Initialize(project='hufpsentinel001')
    print("🌍 Earth Engine Initialized.")
except Exception as e:
    print(f"❌ Error: {e}")
    exit()

# Bounding Box & Quadrants
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

print("🛰️ Accessing Sentinel-1 SAR Radar to map the August 2017 Mega-Flood...")

# Fetch the radar images during the massive Aug 29, 2017 Mumbai flood
s1_flood = ee.ImageCollection('COPERNICUS/S1_GRD') \
    .filterBounds(ee.Geometry.Rectangle([min_lon, min_lat, max_lon, max_lat])) \
    .filterDate('2017-08-28', '2017-09-02') \
    .filter(ee.Filter.listContains('transmitterReceiverPolarisation', 'VV')) \
    .filter(ee.Filter.eq('instrumentMode', 'IW')) \
    .select('VV') \
    .min()

# Radar Thresholding: Water acts like a mirror, bouncing radar away.
# Therefore, pixels darker than -16 decibels are mathematically classified as standing flood water.
flood_target = s1_flood.lt(-16).rename('is_flooded')

print("🚀 Launching 4 Tiled SAR Flood Maps to Google Drive...")

for tile_name, tile_geom in quadrants.items():
    print(f"Submitting ground-truth task for: {tile_name}")
    
    task = ee.batch.Export.image.toDrive(
        image=flood_target.clip(tile_geom),
        description=f'Sentinel_V7_Target_Aug2017_{tile_name}',
        folder='HUFP_Sentinel_Billion_Data',
        fileNamePrefix=f'mumbai_flood_target_2017_{tile_name}',
        region=tile_geom,
        scale=100,
        crs='EPSG:4326',
        maxPixels=1e13,
        fileFormat='GeoTIFF'
    )
    task.start()

print("\n✅ Ground Truth mapping tasks submitted!")
print("👀 Monitor here: https://code.earthengine.google.com/tasks")