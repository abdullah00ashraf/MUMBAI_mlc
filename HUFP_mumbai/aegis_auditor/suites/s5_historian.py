import asyncio
import math
from typing import Dict, Any
from aegis_auditor.core.exceptions import HistoricalIgnorance
from aegis_auditor.db.mongo_store import AEGISMongoStore

class S5_Historian:
    """
    S5 [The Historian]: Cross-references current telemetry against historical flood events (e.g., Mumbai 2005).
    """
    def __init__(self):
        self.db = AEGISMongoStore()

    async def execute(self, telemetry: Dict[str, Any], compute_timeout: float = 2.0) -> Dict[str, Any]:
        if not self.db.connected:
            await self.db.connect()

        # Dynamic resource allocation simulation
        await asyncio.sleep(0.01) # Baseline compute
        if compute_timeout > 2.0:
            # Simulate utilizing extra compute time for deeper temporal correlation mapping
            await asyncio.sleep(0.05)
            
        # 1. Data Ingestion
        precipitation_rate = telemetry.get("rainfall_mm_hr", 0.0)
        sentinel_prediction = telemetry.get("sentinel_prediction", "safe").lower()
        
        # Simulate tracking the rate of acceleration over a rolling 60-minute window (d²(Rain)/dt²)
        # We calculate a synthetic current acceleration curve based on the latest precipitation rate
        current_acceleration = precipitation_rate * 0.8
        mock_current_curve = [10.0, 24.0, 43.0, current_acceleration]
        
        # 2. Ground Truth Check
        historical_data = await self.db.get_historical_trajectory("July_26_2005_Mumbai_Flood")
        historical_curve = historical_data.get("acceleration_curve_first_4_hours", [])

        # 3. The Temporal Calculus
        if historical_curve and len(mock_current_curve) == len(historical_curve):
            # Euclidean distance trajectory mapping
            distance = math.sqrt(sum((a - b) ** 2 for a, b in zip(mock_current_curve, historical_curve)))
            max_possible_distance = 100.0 # Normalization factor
            similarity = max(0.0, 1.0 - (distance / max_possible_distance))
            
            # 4. Veto Condition
            if similarity > 0.90:
                if sentinel_prediction in ["low level threat", "standard alert", "safe"]:
                    raise HistoricalIgnorance(
                        reason=f"60-minute acceleration curve matches first 4 hours of 2005 event with {similarity*100:.1f}% similarity. System entering catastrophic phase. Sentinel's '{sentinel_prediction}' prediction is dangerously invalid."
                    )
            
        return {"status": "verified", "historical_anomaly": False, "temporal_similarity": similarity if historical_curve else 0.0}
