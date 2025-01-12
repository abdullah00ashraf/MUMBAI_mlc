import re
from typing import List, Dict, Any

class AthenaMumbaiNLP:
    """
    Athena NLP module for parsing hydraulic equations and coefficients from academic literature.
    """
    
    @staticmethod
    def extract_academic_constants(text_array: List[str]) -> Dict[str, Any]:
        """
        Parses text arrays using regex tokenization to extract constants such as
        Manning's roughness coefficient (n) or mass balance equations.
        """
        constants = {
            "manning_roughness": [],
            "mass_balance_formulas": [],
            "wave_attenuation_factors": []
        }
        
        # Regex patterns
        manning_regex = re.compile(r"manning(?:'s)?\s*(?:roughness|n)?\s*(?:coefficient)?\s*(?:of)?\s*([0-9]+\.[0-9]+)", re.IGNORECASE)
        formula_regex = re.compile(r"(dH/dt\s*=\s*[^.\n]+|mass\s*conservation\s*:\s*[^.\n]+)", re.IGNORECASE)
        attenuation_regex = re.compile(r"attenuation\s*(?:factor|coefficient)?\s*([0-9]+\.[0-9]+)", re.IGNORECASE)
        
        for text in text_array:
            # Check Manning's roughness coefficient
            manning_match = manning_regex.findall(text)
            for m in manning_match:
                constants["manning_roughness"].append(float(m))
                
            # Check formulas
            formula_match = formula_regex.findall(text)
            for f in formula_match:
                constants["mass_balance_formulas"].append(f.strip())
                
            # Check wave attenuation factors
            attenuation_match = attenuation_regex.findall(text)
            for a in attenuation_match:
                constants["wave_attenuation_factors"].append(float(a))
                
        # Consolidate standard fallbacks if none parsed
        if not constants["manning_roughness"]:
            constants["manning_roughness"].append(0.18) # Default mangrove baseline roughness
        if not constants["wave_attenuation_factors"]:
            constants["wave_attenuation_factors"].append(0.005) # Default attenuation alpha
            
        return constants
