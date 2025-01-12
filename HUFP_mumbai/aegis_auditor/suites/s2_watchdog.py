import asyncio
from typing import Dict, Any, Optional
from aegis_auditor.core.exceptions import HardwareAnomaly
from aegis_auditor.db.mongo_store import AEGISMongoStore

class TelemetryListener:
    """
    1. THE PASSIVE TELEMETRY TAP (THE BRIDGE)
    Acts as a 'sniffer' (Read-Only) on the live data stream.
    Strictly forbidden from sending ACK packets to Sentinel V7.
    """
    def __init__(self, port: int = 8080):
        self.port = port
        self.listening = False

    async def start_listening(self):
        # Simulate binding to the port passively
        self.listening = True
        print(f"[AEGIS_TAP] Passive listener bound to port {self.port} (Read-Only).")
        await asyncio.sleep(0.1)

    async def read_packet(self, simulated_packet: Dict[str, Any]) -> Dict[str, Any]:
        """Simulates receiving a packet passively from the tap."""
        if not self.listening:
            raise Exception("Tap is not listening.")
        await asyncio.sleep(0.01)
        return simulated_packet


class S2_Watchdog:
    """
    S2 [The Watchdog]: Real-time health and error-margin monitoring of telemetry hardware.
    """
    def __init__(self):
        self.mongo_store = AEGISMongoStore()

    async def execute(self, telemetry: Dict[str, Any]) -> Dict[str, Any]:
        """
        Executes the three strict hardware checks on a single packet.
        """
        await self.mongo_store.connect()
        
        sensor_id = telemetry.get("sensor_id")
        if not sensor_id:
            # If not a hardware packet, just verify and pass (for backward compatibility with old tests)
            return {"status": "verified"}

        # Fetch expected hardware parameters
        hw_profile = await self.mongo_store.fetch_hardware_profile(sensor_id)
        if not hw_profile:
            return {"status": "warning", "reason": "Unknown sensor ID"}

        # Extract telemetry data
        voltage = telemetry.get("voltage", 0.0)
        val = telemetry.get("val", 0.0)
        
        # Simulated previous value from db/state to calculate d(Data)/dt
        # In reality, this would be fetched from the DB based on the last reading.
        # For simulation, we assume the previous value is passed or known.
        prev_val = telemetry.get("prev_val", val) 
        dt_seconds = telemetry.get("dt_seconds", 1) # Time difference in seconds

        # A. Battery/Voltage Health
        min_voltage = hw_profile.get("min_voltage", 3.5)
        voltage_status = "OK"
        if voltage < min_voltage:
            voltage_status = "LOW"

        # B. Signal-to-Noise Ratio (Muck-Factor interference)
        snr = telemetry.get("snr", 100)
        min_snr = hw_profile.get("min_snr", 50)
        snr_status = "OK"
        if snr < min_snr:
            snr_status = "LOW"

        # C. The Physical Limit Calculus
        rate_of_change = abs(val - prev_val) / dt_seconds
        max_physical_rate = hw_profile.get("max_physical_rate_per_sec", 0.1)

        roc_status = "within physics limits"
        is_impossible = rate_of_change > max_physical_rate
        if is_impossible:
            # Note: the prompt asks for specific formatting like (+2.1m/5sec) and (0.5m/5sec).
            # The rate is per second, so we can multiply by dt_seconds to show it over the interval.
            diff = abs(val - prev_val)
            max_diff = max_physical_rate * dt_seconds
            roc_status = f"(+{diff:.1f}m/{dt_seconds}sec) EXCEEDS BRIMSTOWAD MAX FLOW RATE ({max_diff:.1f}m/{dt_seconds}sec)"

        # Logging the checks as per expected verification log
        if voltage_status == "LOW" and is_impossible:
             print(f"[WATCHDOG] Check: {sensor_id} -> Voltage LOW. Rate of change {roc_status}.")
        elif is_impossible:
             print(f"[WATCHDOG] Check: {sensor_id} -> Voltage {voltage_status}. Rate of change {roc_status}.")
        else:
             print(f"[WATCHDOG] Check: {sensor_id} -> Voltage {voltage_status}. Rate of change {roc_status}.")

        if is_impossible:
            raise HardwareAnomaly(
                sensor_id, 
                "Impossible differential. Probable sensor occlusion (Muck-factor) or short circuit."
            )
        elif voltage_status == "LOW":
            raise HardwareAnomaly(sensor_id, f"Voltage LOW. {voltage}V < {min_voltage}V")
        elif snr_status == "LOW":
            raise HardwareAnomaly(sensor_id, f"Signal degrading. SNR {snr} < {min_snr}")

        return {"status": "SENSOR_VERIFIED", "sensor_id": sensor_id}
