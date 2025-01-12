"""
PROJECT SALSETTE: THE KONKAN-AEGIS PROTOCOL
MODULE: NEURAL CORE RAW DECOMPILER (BYPASSING TF LOCK)
TARGET: v7_best_brain.keras
OUTPUT: Full Architecture JSON Export
"""

import zipfile
import json
import os

def crack_keras_core(model_path, output_filename="v7_best_brain_topology.json"):
    print(f"\n[SYSTEM] INITIATING RAW DECOMPILE ON: {model_path}")
    
    if not os.path.exists(model_path):
        print(f"[CRITICAL] BRAIN FILE NOT FOUND AT TARGET: {model_path}")
        return
        
    try:
        # A .keras file is a ZIP archive. We bypass the engine completely.
        with zipfile.ZipFile(model_path, 'r') as archive:
            print("[SYSTEM] .KERAS ARCHIVE BREACHED. EXTRACTING METADATA...")
            
            if 'config.json' in archive.namelist():
                with archive.open('config.json') as f:
                    config = json.load(f)
                    
                    print("\n==========================================================")
                    print(" [1] RAW ARCHITECTURE CONFIGURATION")
                    print("==========================================================")
                    
                    class_name = config.get("class_name", "UNKNOWN")
                    registered_name = config.get("registered_name", "UNKNOWN")
                    print(f" [+] CORE CLASS    : {class_name}")
                    print(f" [+] REGISTRY NAME : {registered_name}")
                    
                    print("\n==========================================================")
                    print(" [2] FEATURE DEPENDENCY MATRIX")
                    print("==========================================================")
                    
                    build_config = config.get("build_config", {})
                    input_shape = build_config.get("input_shape", "LOCKED")
                    
                    print(f" [+] INPUT TENSOR SHAPE : {input_shape}")
                    if isinstance(input_shape, list) and len(input_shape) >= 3:
                        print(f" [+] TIME HORIZON       : {input_shape[1]} Timesteps (Hours)")
                        print(f" [+] SENSOR FEATURES    : {input_shape[2]} Discrete Variables")
                    
                    print("\n==========================================================")
                    print(" [3] EXPORTING FULL TOPOLOGY TO ROOT FOLDER")
                    print("==========================================================")
                    
                    # Write the fully uncompressed JSON payload to the root directory
                    with open(output_filename, 'w') as out_file:
                        json.dump(config, out_file, indent=4)
                        
                    print(f" [+] FULL ARCHITECTURE SAVED TO : {output_filename}")
                    
            else:
                print("[CRITICAL] config.json NOT FOUND IN ARCHIVE.")
                
        print("\n[SYSTEM] RAW DECOMPILE COMPLETE. DEPENDENCIES VERIFIED.\n")
        
    except Exception as e:
        print(f"\n[CRITICAL FAILURE] ARCHIVE CORRUPTED OR ENCRYPTED:")
        print(f"ERROR: {e}")

if __name__ == "__main__":
    TARGET_MODEL = "models/v7_best_brain.keras" 
    # This will drop the file right into C:\MUMBAI_mlc\HUFP_mumbai
    OUTPUT_FILE = "v7_best_brain_topology.json" 
    crack_keras_core(TARGET_MODEL, OUTPUT_FILE)