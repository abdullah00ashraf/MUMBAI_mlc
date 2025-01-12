import asyncio
from aegis_auditor.db.mongo_store import AEGISMongoStore
from aegis_auditor.judge_overseer import JudgeOverseer

async def genesis_boot_sequence():
    """
    Test script to verify the AEGIS Initialization Criteria:
    - Boundary walls / Uni-directional Data Flow
    - Judge layer encapsulates parallel Suites
    - Autonomic Gap-Detection (Humanitarian Empathy)
    """
    print("=== INITIATING AEGIS GENESIS BOOT ===")
    
    # 1. Establish Data Boundaries
    mongo_store = AEGISMongoStore()
    await mongo_store.connect()
    
    # 2. Instantiate the Judge Overseer (which encapsulates S1-S6)
    judge = JudgeOverseer()
    
    # 3. Read telemetry unidirectionally (simulated from Sentinel V7)
    telemetry = await mongo_store.fetch_sentinel_telemetry()
    print(f"[OBSERVATION] Fetched Sentinel Telemetry: {telemetry}")
    
    # 4. Execute Audit
    print("\n[AUDIT] Starting Judge/Jury Validation...")
    audit_result = await judge.execute_audit(telemetry)
    print(f"\n[FINAL OUTPUT] {audit_result}")
    
    # 5. Write-Only Integrity
    await mongo_store.append_audit_record(audit_result)
    
    print("\n=== BOOT SEQUENCE COMPLETE ===")

if __name__ == "__main__":
    # Ensure this runs in Python 3.7+ 
    asyncio.run(genesis_boot_sequence())
