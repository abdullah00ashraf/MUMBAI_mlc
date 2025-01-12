import os
import pystac
import rasterio
import numpy as np
from datetime import datetime

class CoastalGuardrails:
    def __init__(self):
        # Resolve STAC catalog path relative to script location
        self.script_dir = os.path.dirname(os.path.abspath(__file__))
        self.catalog_path = os.path.join(
            os.path.dirname(os.path.dirname(self.script_dir)),
            "data", "stac", "catalog.json"
        )
        self.catalog = None
        if os.path.exists(self.catalog_path):
            self.catalog = pystac.Catalog.from_file(self.catalog_path)

    def load_bands(self, item: pystac.Item) -> dict:
        """
        Uses pystac to resolve the assets and rasterio to read them as float32.
        """
        bands = ["blue", "green", "red", "nir", "swir"]
        data = {}
        
        # Base directory of the item to resolve relative hrefs
        item_dir = os.path.dirname(item.get_self_href())
        
        for b in bands:
            asset = item.assets.get(b)
            if not asset:
                raise FileNotFoundError(f"Asset '{b}' not found in STAC item '{item.id}'")
            
            # Resolve relative paths
            href = asset.href
            if not os.path.isabs(href):
                href = os.path.normpath(os.path.join(item_dir, href))
                
            with rasterio.open(href) as src:
                data[b] = src.read(1).astype('float32')
                
        return data

    def select_best_item(self, target_polygon_width_m: float) -> pystac.Item:
        """
        Mixed-Pixel Mitigation:
        If target shadow zone is narrower than 30 meters, prioritize PlanetScope
        (which has high resolution, e.g. 3m) over Sentinel-2 (10m) to avoid mixed-pixel contamination.
        """
        if not self.catalog:
            raise FileNotFoundError("STAC Catalog is not loaded.")
            
        items = list(self.catalog.get_all_items())
        if not items:
            raise ValueError("No items found in STAC Catalog.")
            
        if target_polygon_width_m < 30.0:
            # Look for PlanetScope first
            for item in items:
                platform = item.properties.get("platform", "").lower()
                if "planet" in platform or "planetscope" in platform:
                    print(f"[GUARDRAILS] Area width {target_polygon_width_m}m is < 30m. PlanetScope selected for mixed-pixel mitigation.")
                    return item
                    
        # Default or fallback
        for item in items:
            platform = item.properties.get("platform", "").lower()
            if "sentinel-2" in platform or "sentinel" in platform:
                print(f"[GUARDRAILS] Selecting Sentinel-2 standard resolution item: {item.id}.")
                return item
                
        return items[0]

    def calculate_spectral_indices(self, bands_data: dict) -> dict:
        """
        Computes NDVI, EVI, and MNDWI using numpy arithmetic with division-by-zero protection.
        """
        blue = bands_data["blue"]
        green = bands_data["green"]
        red = bands_data["red"]
        nir = bands_data["nir"]
        swir = bands_data["swir"]
        
        # NDVI: (NIR - Red) / (NIR + Red)
        ndvi = (nir - red) / (nir + red + 1e-8)
        
        # EVI: 2.5 * (NIR - Red) / (NIR + 6 * Red - 7.5 * Blue + 1)
        evi = 2.5 * ((nir - red) / (nir + 6.0 * red - 7.5 * blue + 1.0 + 1e-8))
        
        # MNDWI: (Green - SWIR) / (Green + SWIR)
        mndwi = (green - swir) / (green + swir + 1e-8)
        
        return {"ndvi": ndvi, "evi": evi, "mndwi": mndwi}

    def detect_canopy_loss(self, ndvi_array: np.ndarray, baseline_ndvi: float) -> dict:
        """
        Detects rapid canopy loss against a historical baseline.
        """
        current_mean_ndvi = float(np.mean(ndvi_array))
        drop_pct = ((baseline_ndvi - current_mean_ndvi) / baseline_ndvi) * 100.0 if baseline_ndvi > 0 else 0.0
        
        loss_detected = drop_pct > 30.0 # 30% drop threshold
        return {
            "mean_ndvi": current_mean_ndvi,
            "baseline_ndvi": baseline_ndvi,
            "drop_percentage": round(drop_pct, 2),
            "canopy_loss_detected": loss_detected
        }

    def check_tidal_disconnection(self, predicted_tide_m: float, mndwi_array: np.ndarray) -> dict:
        """
        Cross-references predicted astronomical tide height with water indices (MNDWI).
        If tide is high (>3.5m) and MNDWI indicates dry ground (mean <= 0.0),
        flags a Hydrological Disconnection Anomaly (illegal debris dumping).
        """
        mean_mndwi = float(np.mean(mndwi_array))
        is_dry = mean_mndwi <= 0.0
        is_high_tide = predicted_tide_m > 3.5
        
        anomaly = is_high_tide and is_dry
        return {
            "predicted_tide_m": predicted_tide_m,
            "mean_mndwi": mean_mndwi,
            "is_dry": is_dry,
            "hydrological_disconnection_anomaly": anomaly
        }

    def simulate_wave_damping(
        self,
        mangrove_density_pct: float,
        rainfall_mm_hr: float,
        tide_height_m: float
    ) -> dict:
        """
        PINN Wave Attenuation and Inundation Depth Simulator.
        Models wave velocity damping and inundation depth mapping:
        - Baseline (100% density): wave damping is high, flood risk is low.
        - Degraded (0% density): wave damping is low, flood risk is high.
        """
        # Physics constants
        g = 9.81  # gravity m/s^2
        # Deep water wave velocity (sqrt(g * depth))
        h_base = max(0.5, tide_height_m + (rainfall_mm_hr / 100.0) * 0.2)
        v_unattenuated = np.sqrt(g * h_base)
        
        # Manning's roughness coefficient (n) based on density
        # Mangrove baseline (100%): n = 0.18
        # Bare mudflat/degraded: n = 0.025
        n_manning = 0.025 + (mangrove_density_pct / 100.0) * (0.18 - 0.025)
        
        # Wave attenuation factor: exponential decay over a 500m buffer
        # Attenuation coefficient alpha scales with manning's n
        alpha = 0.005 * (n_manning / 0.025)
        v_attenuated = v_unattenuated * np.exp(-alpha * 500.0)
        
        # Base wave velocity values at 100% vs target density
        n_100 = 0.18
        alpha_100 = 0.005 * (n_100 / 0.025)
        v_baseline = v_unattenuated * np.exp(-alpha_100 * 500.0)
        v_degraded = v_attenuated
        
        delta_wave_velocity = float(v_baseline - v_degraded)
        
        # Inundation Depth Calculation (Cross-referencing DEM effect)
        # Without mangroves, water runs up further inland.
        # Shift in inundation depth matches mass accumulation scaling:
        # Depth d = h_base * (1 + (v_unattenuated - v_attenuated)/v_unattenuated)
        d_baseline = h_base * (1.0 + (v_unattenuated - v_baseline) / v_unattenuated * 0.1)
        d_degraded = h_base * (1.0 + (v_unattenuated - v_degraded) / v_unattenuated * 0.1)
        
        # If degraded density has less friction, inundation is deeper
        if mangrove_density_pct < 100.0:
            # Friction reduction increases water buildup inland
            friction_loss = (100.0 - mangrove_density_pct) / 100.0
            d_degraded += 0.8 * friction_loss  # Up to 0.8m extra flood depth
            
        delta_inundation_depth = float(d_degraded - d_baseline)
        
        return {
            "manning_roughness_n": round(n_manning, 4),
            "attenuated_wave_velocity_m_s": round(float(v_attenuated), 3),
            "unattenuated_wave_velocity_m_s": round(float(v_unattenuated), 3),
            "wave_velocity_delta_m_s": round(delta_wave_velocity, 3),
            "baseline_inundation_depth_m": round(float(d_baseline), 3),
            "degraded_inundation_depth_m": round(float(d_degraded), 3),
            "delta_inundation_depth_m": round(delta_inundation_depth, 3)
        }
