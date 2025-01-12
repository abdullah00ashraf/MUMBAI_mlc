import numpy as np
from typing import Tuple, Dict, Any

class TopographyAuditor:
    """
    Topography Auditor for validating DEM elevations and finding anomalies.
    """
    
    @staticmethod
    def audit_field_elevations(
        dem_matrix: np.ndarray,
        expected_bounds: Tuple[float, float]
    ) -> Dict[str, Any]:
        """
        Inspects digital elevation model matrices for out-of-bounds topological outliers.
        This helps identify illegal landfills/debris dumps or excavation depressions.
        """
        min_expected, max_expected = expected_bounds
        
        # Identify outliers
        below_min_mask = dem_matrix < min_expected
        above_max_mask = dem_matrix > max_expected
        
        below_count = int(np.sum(below_min_mask))
        above_count = int(np.sum(above_max_mask))
        
        # Calculate indices of outliers
        illegal_landfill_indices = np.argwhere(above_max_mask).tolist()
        excavation_depression_indices = np.argwhere(below_min_mask).tolist()
        
        outliers_detected = below_count > 0 or above_count > 0
        
        return {
            "total_pixels_audited": int(dem_matrix.size),
            "outliers_detected": outliers_detected,
            "illegal_landfills_detected_count": above_count,
            "excavation_depressions_detected_count": below_count,
            "illegal_landfill_locations": illegal_landfill_indices[:50], # Cap at 50 to avoid massive payloads
            "excavation_depression_locations": excavation_depression_indices[:50],
            "mean_elevation_m": float(np.mean(dem_matrix)),
            "max_elevation_m": float(np.max(dem_matrix)),
            "min_elevation_m": float(np.min(dem_matrix))
        }
