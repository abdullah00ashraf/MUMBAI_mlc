import asyncio
from aegis_auditor.suites.s2_watchdog import TelemetryListener, S2_Watchdog
from aegis_auditor.core.exceptions import HardwareAnomaly

async def verify_watchdog_bridge():
    print("=== INITIATING WATCHDOG TELEMETRY BRIDGE ===")
    
    # 1. Start Passive Listener
    listener = TelemetryListener(port=8080)
    await listener.start_listening()
    
    watchdog = S2_Watchdog()
    print("[WATCHDOG] Loaded hardware profiles from AEGIS_DB.\n")

    # Packet 1: Healthy
    # Simulate a 2mm change over 5 mins (300 seconds)
    packet_1 = {
        'sensor_id': 'WARD_K_RAIN_01', 
        'val': 45.2, 
        'prev_val': 43.2, 
        'dt_seconds': 300, 
        'voltage': 4.1, 
        'timestamp': '12:41:00'
    }
    
    # Packet 2: Impossible
    # Simulate a 2.1m change over 5 seconds
    packet_2 = {
        'sensor_id': 'MITHI_LIDAR_04', 
        'val': 6.8, 
        'prev_val': 4.7, 
        'dt_seconds': 5, 
        'voltage': 3.2, 
        'timestamp': '12:41:05'
    }

    packets = [packet_1, packet_2]

    for packet in packets:
        print(f"[STREAM IN] Packet: {packet}")
        try:
            # Read from tap
            data = await listener.read_packet(packet)
            
            # Watchdog audit
            result = await watchdog.execute(data)
            print(f"[WATCHDOG] Status: {result.get('status')}.\n")
            
        except HardwareAnomaly as ha:
            print(f"[WATCHDOG FAULT] HardwareAnomaly triggered! Reason: {ha.reason}")
            print("\n[JUDGE] Audit Halted. V_audit = 0 due to Watchdog (S_2) Hardware Veto.")
            print("[AEGIS_DB] Hardware failure logged. Alerting Resource Manager.\n")

if __name__ == "__main__":
    asyncio.run(verify_watchdog_bridge())
