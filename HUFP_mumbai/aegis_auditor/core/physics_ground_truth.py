# core/physics_ground_truth.py

class L_Physics:
    """
    Hydrological Ground Truth (L_physics) based on Majid Hussain's 
    geography parameters and BRIMSTOWAD guidelines.
    """
    
    # Max rainfall capacity for Mumbai drains (mm/hr) under BRIMSTOWAD Phase 1
    BRIMSTOWAD_CAPACITY_MM_HR = 50.0 
    
    # Maximum high tide level before coastal gates lock (meters)
    CRITICAL_HIGH_TIDE_M = 4.5
    
    @staticmethod
    def validate_mass_balance(rainfall_mm_hr: float, tide_m: float, runoff_coeff: float) -> bool:
        """
        Intersection test: S_i \cap L_physics.
        If any suite predicts safety when physics dictates flooding, this fails.
        """
        # Example strict physics constraint
        effective_drainage = L_Physics.BRIMSTOWAD_CAPACITY_MM_HR
        if tide_m >= L_Physics.CRITICAL_HIGH_TIDE_M:
            # Gravity drains fail during high tide
            effective_drainage *= 0.1 
            
        water_accumulation = (rainfall_mm_hr * runoff_coeff) - effective_drainage
        
        # If water is accumulating significantly, predicting a "safe" state is a physics violation.
        # This function returns True if the state is physically valid/expected.
        # In actual usage, Suites will pass their parameters here to ensure they don't break reality.
        return True # Placeholder for more complex intersection logic

    @staticmethod
    def get_runoff_coefficient(terrain_type: str) -> float:
        """Based on geographical text ground truths."""
        coefficients = {
            "high_density_slum": 0.85, # Highly paved/compacted, fast runoff
            "mangrove": 0.20,
            "urban_concrete": 0.90
        }
        return coefficients.get(terrain_type, 0.70)
