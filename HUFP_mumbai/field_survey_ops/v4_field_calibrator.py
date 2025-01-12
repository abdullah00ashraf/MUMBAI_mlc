import os
import time
import json
import requests
import pandas as pd
import hashlib
import math
import threading
import subprocess
from datetime import datetime

# ==============================================================================
# 🌊 SENTINEL V7: AUTONOMOUS FIELD DAEMON (v5.0)
# ==============================================================================

C = {
    "R": "\033[91m", "G": "\033[92m", "Y": "\033[93m", 
    "B": "\033[94m", "C": "\033[96m", "W": "\033[0m", "BOLD": "\033[1m"
}

class SentinelDaemon:
    def __init__(self, output_dir="field_data"):
        self.output_dir = output_dir
        os.makedirs(self.output_dir, exist_ok=True)
        self.db_path = os.path.join(self.output_dir, "v7_ground_truth_ledger.csv")
        self.geo_path = os.path.join(self.output_dir, "v7_spatial_map.geojson")
        self.state_path = os.path.join(self.output_dir, "v7_daemon_state.json")
        
        self.is_running = False
        self.polling_interval = 5 # minutes
        
        self.reference_sensors = {
            "Colaba_IMD": (18.9067, 72.8147),
            "Santacruz_IMD": (19.0860, 72.8170),
            "Dadar_Hindmata": (19.0150, 72.8425)
        }
        self._init_ledger()
        self.state = self._load_state()

    def _init_ledger(self):
        if not os.path.exists(self.db_path):
            df = pd.DataFrame(columns=[
                "timestamp", "lat", "lon", "elevation_m", "nearest_sensor_km",
                "api_rainfall_mm", "physical_rain_mm",
                "api_tide_m", "physical_depth_mm",
                "rainfall_delta", "drift_flag", "architect_notes", "sha256_hash"
            ])
            df.to_csv(self.db_path, index=False)

    def _load_state(self):
        if os.path.exists(self.state_path):
            try:
                with open(self.state_path, 'r') as f: return json.load(f)
            except: pass
        return {"last_lat": 19.0150, "last_lon": 72.8425}

    def _save_state(self, lat, lon):
        self.state = {"last_lat": lat, "last_lon": lon}
        try:
            with open(self.state_path, 'w') as f: json.dump(self.state, f)
        except: pass

    def get_hardware_gps(self):
        """Attempts to hook into mobile GPS via Termux API."""
        try:
            result = subprocess.run(['termux-location'], capture_output=True, text=True, timeout=5)
            if result.returncode == 0:
                data = json.loads(result.stdout)
                return float(data.get("latitude")), float(data.get("longitude"))
        except:
            pass # Fallback to static state if not on mobile/Termux
        return self.state['last_lat'], self.state['last_lon']

    def fetch_digital_twin(self, lat, lon):
        try:
            w_url = f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&current=precipitation&timezone=Asia%2FKolkata"
            api_rain = requests.get(w_url, timeout=5).json().get('current', {}).get('precipitation', 0.0)
            m_url = f"https://marine-api.open-meteo.com/v1/marine?latitude=18.9&longitude=72.8&current=ocean_height&timezone=Asia%2FKolkata"
            api_tide = requests.get(m_url, timeout=5).json().get('current', {}).get('ocean_height', 0.0)
            e_url = f"https://api.open-meteo.com/v1/elevation?latitude={lat}&longitude={lon}"
            api_elev = requests.get(e_url, timeout=5).json().get('elevation', [0.0])[0]
            return api_rain, api_tide, api_elev
        except:
            return None, None, None

    def update_geojson(self, df_record):
        features = []
        if os.path.exists(self.geo_path):
            try:
                with open(self.geo_path, 'r') as f: features = json.load(f).get("features", [])
            except: pass
        features.append({
            "type": "Feature",
            "geometry": {"type": "Point", "coordinates": [float(df_record['lon']), float(df_record['lat'])]},
            "properties": df_record
        })
        with open(self.geo_path, 'w') as f: json.dump({"type": "FeatureCollection", "features": features}, f, indent=2)

    def write_observation(self, lat, lon, api_data, phys_rain, phys_depth, notes, is_passive=False):
        api_rain, api_tide, api_elev = api_data
        
        delta_flag = "PASSIVE_SYNC" if is_passive else "MANUAL_SYNC"
        rain_delta = 0.0
        
        if api_rain is not None:
            rain_delta = round(phys_rain - api_rain, 2)
            if rain_delta > 5.0: delta_flag = f"SEVERE_UNDERSHOOT (+{rain_delta}mm error)"
            elif rain_delta < -2.0: delta_flag = f"GHOST_RAIN ({rain_delta}mm error)"
        else:
            delta_flag = "NETWORK_BLACKOUT"

        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        record_raw = f"{timestamp}|{lat}|{lon}|{phys_rain}|{phys_depth}|{api_rain}"
        crypto_hash = hashlib.sha256(record_raw.encode('utf-8')).hexdigest()

        record = {
            "timestamp": timestamp, "lat": lat, "lon": lon,
            "elevation_m": api_elev if api_elev else "OFFLINE",
            "nearest_sensor_km": "Auto-Tracked",
            "api_rainfall_mm": api_rain if api_rain else "OFFLINE",
            "physical_rain_mm": phys_rain,
            "api_tide_m": api_tide if api_tide else "OFFLINE",
            "physical_depth_mm": phys_depth,
            "rainfall_delta": rain_delta,
            "drift_flag": delta_flag,
            "architect_notes": notes,
            "sha256_hash": crypto_hash
        }
        
        df = pd.DataFrame([record])
        df.to_csv(self.db_path, mode='a', header=not os.path.exists(self.db_path), index=False)
        self.update_geojson(record)
        return delta_flag, crypto_hash, api_rain

    def _daemon_loop(self):
        """Runs continuously in the background."""
        while self.is_running:
            lat, lon = self.get_hardware_gps()
            self._save_state(lat, lon)
            api_data = self.fetch_digital_twin(lat, lon)
            
            if api_data[0] is not None and api_data[0] > 10.0:
                print(f"\n\a{C['R']}⚠️ ACOUSTIC ALARM: API DETECTS HEAVY RAIN (>10mm). VERIFY PHYSICAL REALITY!{C['W']}")
            
            # Passive log assumes physical reality matches API if user doesn't intervene
            assumed_phys_rain = api_data[0] if api_data[0] else 0.0
            flag, hash_code, _ = self.write_observation(lat, lon, api_data, assumed_phys_rain, 0.0, "Auto-Daemon Log", is_passive=True)
            
            print(f"\n{C['C']}[DAEMON] {datetime.now().strftime('%H:%M')} | Auto-Log Secured | Status: {flag}{C['W']}\nSentinel>", end=" ", flush=True)
            
            for _ in range(self.polling_interval * 60):
                if not self.is_running: break
                time.sleep(1)

    def start_daemon(self):
        self.is_running = True
        daemon_thread = threading.Thread(target=self._daemon_loop, daemon=True)
        daemon_thread.start()
        
        print(f"\n{C['BOLD']}{C['G']}🟢 DAEMON ACTIVE. Running autonomously in background.{C['W']}")
        print(f"{C['Y']}The software will silently track GPS and log API state every {self.polling_interval} mins.{C['W']}")
        print(f"{C['BOLD']}Commands: [O]verride (Log physical anomaly) | [Q]uit{C['W']}\n")
        
        while self.is_running:
            try:
                cmd = input("Sentinel> ").strip().lower()
                if cmd == 'q':
                    print(f"{C['R']}Initiating safe shutdown...{C['W']}")
                    self.is_running = False
                    break
                elif cmd == 'o':
                    self.manual_override()
            except KeyboardInterrupt:
                self.is_running = False
                break

    def manual_override(self):
        """Foreground interrupt for the field engineer."""
        print(f"\n{C['B']}X{'='*50}X{C['W']}")
        print(f"{C['BOLD']} 🛑 TACTICAL OVERRIDE INITIATED {C['W']}")
        
        lat, lon = self.get_hardware_gps()
        print(f"📡 Current Target: [{lat}, {lon}]")
        
        api_data = self.fetch_digital_twin(lat, lon)
        
        phys_rain = input(f"{C['Y']}Actual Rainfall (mm/hr): {C['W']}").strip()
        phys_rain = float(phys_rain) if phys_rain else 0.0
        
        phys_depth = input(f"{C['Y']}Current water depth (mm): {C['W']}").strip()
        phys_depth = float(phys_depth) if phys_depth else 0.0
        
        notes = input(f"{C['Y']}Architect Notes: {C['W']}").strip() or "Manual Anomaly Override"
        
        flag, hash_code, _ = self.write_observation(lat, lon, api_data, phys_rain, phys_depth, notes, is_passive=False)
        
        color = C['R'] if "UNDERSHOOT" in flag or "GHOST" in flag else C['G']
        print(f"\n{C['BOLD']}OVERRIDE VERDICT: {color}{flag}{C['W']}")
        print(f"{C['G']}💾 GROUND TRUTH LOCKED. Resuming background daemon...{C['W']}")
        print(f"{C['B']}X{'='*50}X{C['W']}\n")

if __name__ == "__main__":
    node = SentinelDaemon()
    node.start_daemon()