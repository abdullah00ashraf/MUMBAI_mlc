import asyncio
import aiohttp
import pyarrow as pa
import pyarrow.parquet as pq
import datetime
import logging
import os

# Configure Logging
LOG_FILE = "ingestion.log"
logging.basicConfig(
    filename=LOG_FILE,
    level=logging.INFO,
    format="%(asctime)s - [%(levelname)s] - %(message)s"
)

# Configuration
MUMBAI_LAT = 18.9
MUMBAI_LON = 72.8
POLL_INTERVAL_SECONDS = 300 # 5 minutes
PARQUET_FILE = os.path.join("data", "live_telemetry.parquet")

# Open-Meteo API Endpoints
# Using current weather for precipitation and marine for tides.
WEATHER_URL = f"https://api.open-meteo.com/v1/forecast?latitude={MUMBAI_LAT}&longitude={MUMBAI_LON}&current=precipitation&timezone=auto"
MARINE_URL = f"https://marine-api.open-meteo.com/v1/marine?latitude={MUMBAI_LAT}&longitude={MUMBAI_LON}&current=ocean_wave_height&timezone=auto"

# Define Parquet Schema
SCHEMA = pa.schema([
    ("timestamp", pa.string()),
    ("lat", pa.float32()),
    ("lon", pa.float32()),
    ("rain_mm", pa.float32()),
    ("tide_m", pa.float32())
])

async def fetch_json(session: aiohttp.ClientSession, url: str) -> dict:
    try:
        async with session.get(url, timeout=10) as response:
            response.raise_for_status()
            return await response.json()
    except asyncio.TimeoutError:
        logging.error(f"Timeout fetching from {url}")
        return {}
    except Exception as e:
        logging.error(f"Error fetching from {url}: {e}")
        return {}

# Writer Queue
write_queue = asyncio.Queue()

def write_sync_atomic(data: dict):
    os.makedirs(os.path.dirname(PARQUET_FILE), exist_ok=True)
    table = pa.Table.from_pylist([data], schema=SCHEMA)
    
    if not os.path.exists(PARQUET_FILE):
        # Create new file
        pq.write_table(table, PARQUET_FILE, compression='snappy')
        logging.info("Created new Parquet file.")
    else:
        # Atomic read-concatenate-write cycle
        tmp_file = PARQUET_FILE + ".tmp"
        try:
            existing_table = pq.read_table(PARQUET_FILE)
            combined_table = pa.concat_tables([existing_table, table])
            pq.write_table(combined_table, tmp_file, compression='snappy')
            os.replace(tmp_file, PARQUET_FILE)
            logging.info(f"Appended telemetry atomically: {data}")
        except Exception as e:
            if os.path.exists(tmp_file):
                try:
                    os.remove(tmp_file)
                except:
                    pass
            logging.error(f"Failed to append to parquet file atomically: {e}")

async def parquet_writer_worker():
    logging.info("Starting Async Parquet Writer Worker...")
    while True:
        data = await write_queue.get()
        try:
            await asyncio.to_thread(write_sync_atomic, data)
        except Exception as e:
            logging.error(f"Error in parquet_writer_worker: {e}")
        finally:
            write_queue.task_done()

async def append_to_parquet(data: dict):
    """
    Push incoming telemetry record to the writer queue.
    """
    await write_queue.put(data)


async def ingestion_loop():
    logging.info("Starting Zero-Latency Live Ingestion Daemon...")
    # Start the async writer worker task in the background
    asyncio.create_task(parquet_writer_worker())
    async with aiohttp.ClientSession() as session:
        while True:
            logging.info("Fetching real-time telemetry...")
            
            # Fetch concurrently
            weather_task = asyncio.create_task(fetch_json(session, WEATHER_URL))
            marine_task = asyncio.create_task(fetch_json(session, MARINE_URL))
            
            weather_data, marine_data = await asyncio.gather(weather_task, marine_task)
            
            # Extract
            try:
                rain_mm = float(weather_data.get("current", {}).get("precipitation", 0.0))
            except (ValueError, TypeError):
                rain_mm = 0.0
                
            try:
                # Assuming ocean_wave_height as proxy for tide variation in this API demo
                tide_m = float(marine_data.get("current", {}).get("ocean_wave_height", 2.5))
            except (ValueError, TypeError):
                tide_m = 2.5
                
            timestamp = datetime.datetime.now(datetime.timezone.utc).isoformat()
            
            record = {
                "timestamp": timestamp,
                "lat": float(MUMBAI_LAT),
                "lon": float(MUMBAI_LON),
                "rain_mm": rain_mm,
                "tide_m": tide_m
            }
            
            # Append non-blocking
            await append_to_parquet(record)
            
            # Wait for next poll
            await asyncio.sleep(POLL_INTERVAL_SECONDS)

if __name__ == "__main__":
    try:
        asyncio.run(ingestion_loop())
    except KeyboardInterrupt:
        logging.info("Daemon gracefully shutdown by user.")
