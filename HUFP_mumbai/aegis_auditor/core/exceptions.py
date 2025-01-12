class AEGISBaseException(Exception):
    """Base exception for all AEGIS internal faults."""
    pass

class SuiteError(AEGISBaseException):
    """
    Localized exception raised when a single suite encounters a failure.
    Must never cause a system-wide collapse (STD_2).
    """
    def __init__(self, suite_id: str, message: str):
        self.suite_id = suite_id
        super().__init__(f"[{suite_id} FAILURE] {message}")


class RequestForInformation(AEGISBaseException):
    """
    Humanitarian Empathy / Gap-Detection Trigger (STD_5).
    Raised when pre-processed raw data provides insufficient resolution
    for a life-critical prediction. AEGIS halts and outputs this RFI
    instead of guessing.
    """
    def __init__(self, missing_parameter: str, context: str):
        self.missing_parameter = missing_parameter
        self.context = context
        super().__init__(f"RFI Triggered: Missing > 95% confidence on {missing_parameter}. Context: {context}")

class HardwareAnomaly(SuiteError):
    """
    Triggered by S2_Watchdog when hardware physics limits are broken
    (e.g., impossible rate of change, battery decay).
    """
    def __init__(self, sensor_id: str, reason: str):
        self.sensor_id = sensor_id
        self.reason = reason
        super().__init__("S2", f"HardwareAnomaly [{sensor_id}]: {reason}")

class TransitContradiction(SuiteError):
    """
    Triggered by S4_Predictor when localized physics guarantees flooding,
    contradicting Sentinel V7's 'Safe' prediction.
    """
    def __init__(self, node_id: str, reason: str):
        self.node_id = node_id
        self.reason = reason
        super().__init__("S4", f"TransitContradiction [{node_id}]: {reason}")

class HistoricalIgnorance(SuiteError):
    """
    Triggered by S5_Historian when current telemetry matches historical 
    catastrophes (e.g., 2005 Mumbai Flood) but Sentinel V7 outputs a low threat level.
    """
    def __init__(self, reason: str):
        self.reason = reason
        super().__init__("S5", f"HistoricalIgnorance: {reason}")
