import torch
import torch.optim as optim
from torch.utils.data import Dataset, DataLoader
import sqlite3
import pandas as pd
import numpy as np
import os
import time
from sklearn.preprocessing import MinMaxScaler

import sys
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../models')))
from bi_lstm_mumbai_v1 import SentinelMumbaiPINN, PINN_Loss

# --- Configuration ---
DB_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../data/mumbai_coastal_vault.db'))
MODEL_SAVE_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), '../models/sentinel_mumbai_v1.pt'))
SEQ_LENGTH = 24  
EPOCHS = 100
TARGET_MAE = 0.0004
DEVICE = torch.device("cpu")

# --- INTEL i5-1235U ALDER LAKE OPTIMIZATIONS ---
torch.set_num_threads(4) # Pin to the 4 P-Core threads
torch.set_flush_denormal(True) # Prevents CPU slowdowns

PHYSICAL_BATCH_SIZE = 16     
ACCUMULATION_STEPS = 16      # 16 x 16 = 256 Effective Batch Size

class MumbaiCoastalDataset(Dataset):
    def __init__(self, db_path, seq_length):
        print("[SYS] Extracting Tactical Telemetry (Monsoon Filtering Active)...")
        conn = sqlite3.connect(db_path)
        
        # MASSIVE EFFICIENCY GAIN: We drop the sunny days. 
        query = """
            SELECT 
                t.precip_mm_hr, t.cumulative_rain_24h, t.tidal_height_m, 
                w.avg_elevation_m, w.impermeability_index, w.drainage_capacity_m3_s, w.distance_to_coast_m,
                0.0 AS temp_placeholder, 0.0 AS soil_placeholder, 
                t.actual_flood_depth_m
            FROM telemetry_mesh t
            JOIN ward_topography w ON t.ward_id = w.ward_id
            WHERE t.precip_mm_hr > 0.0 OR t.tidal_height_m > 3.0
            ORDER BY t.ward_id, t.timestamp
        """
        df = pd.read_sql_query(query, conn)
        conn.close()

        features = df.iloc[:, :-1].values
        targets = df.iloc[:, -1].values
        
        print(f"[SYS] Filtered Dataset Size: {len(df)} critical risk records.")

        self.scaler_x = MinMaxScaler()
        self.scaler_y = MinMaxScaler()
        
        features_scaled = self.scaler_x.fit_transform(features)
        targets_scaled = self.scaler_y.fit_transform(targets.reshape(-1, 1))

        num_samples = len(features_scaled) - seq_length
        idx = np.arange(seq_length)[None, :] + np.arange(num_samples)[:, None]
        
        self.X = torch.FloatTensor(features_scaled[idx])
        self.y = torch.FloatTensor(targets_scaled[seq_length:])

    def __len__(self):
        return len(self.X)

    def __getitem__(self, idx):
        return self.X[idx], self.y[idx]

def initiate_neural_forge():
    print(f"=== INITIATING SENTINEL V7 NEURAL FORGE ===")
    print(f"[HW] Active Compute Device: {DEVICE} (Restricted to 4 P-Core Threads)")
    print(f"[HW] Memory Opt: Micro-Batch {PHYSICAL_BATCH_SIZE} | Effective Batch {PHYSICAL_BATCH_SIZE * ACCUMULATION_STEPS}")
    print(f"[HW] Precision Opt: Native Float32 (Maximum Stability)")

    dataset = MumbaiCoastalDataset(DB_PATH, SEQ_LENGTH)
    
    dataloader = DataLoader(dataset, batch_size=PHYSICAL_BATCH_SIZE, shuffle=True, drop_last=True, num_workers=0, pin_memory=False)
    
    total_batches = len(dataloader)
    print(f"[OK] Dataloader ready. Total Micro-Batches/Epoch: {total_batches}")

    # Initialize 26.8 Million Parameter Model
    model = SentinelMumbaiPINN(input_dim=9, hidden_dim=512, num_layers=6).to(DEVICE)
    
    # --- CHECKPOINT RECOVERY SYSTEM ---
    if os.path.exists(MODEL_SAVE_PATH):
        print(f"[SYS] Locating previous neural checkpoint...")
        # weights_only=True is the modern secure way to load PyTorch dicts
        model.load_state_dict(torch.load(MODEL_SAVE_PATH, map_location=DEVICE, weights_only=True))
        print(f"[OK] Weights loaded successfully. Resuming optimization.")
    else:
        print(f"[SYS] No existing checkpoint found. Initiating fresh parameters.")
    # ----------------------------------

    pinn_loss_fn = PINN_Loss(alpha=1.0, beta=10.0) 
    
    optimizer = optim.AdamW(model.parameters(), lr=0.001, weight_decay=1e-4)
    scheduler = optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=EPOCHS, eta_min=1e-6)

    print("\n[SYS] Commencing Deep Learning Protocol...")
    best_loss = float('inf')
    forge_start = time.time()

    for epoch in range(EPOCHS):
        model.train()
        total_data_loss = 0.0
        total_phys_loss = 0.0
        total_mae = 0.0
        
        epoch_start = time.time()
        batch_start_time = time.time()
        
        optimizer.zero_grad()

        for batch_idx, (X_batch, y_batch) in enumerate(dataloader):
            
            # --- NATIVE FLOAT 32 MATH ---
            predictions = model(X_batch)
            
            rain_intensity = X_batch[:, -1, 0:1] 
            tidal_height = X_batch[:, -1, 2:3]
            
            loss, d_loss, p_loss = pinn_loss_fn(predictions, y_batch, rain_intensity, tidal_height)
            loss = loss / ACCUMULATION_STEPS

            loss.backward()
            
            if ((batch_idx + 1) % ACCUMULATION_STEPS == 0) or (batch_idx + 1 == total_batches):
                torch.nn.utils.clip_grad_norm_(model.parameters(), max_norm=1.0)
                optimizer.step()
                optimizer.zero_grad() 
            
            total_data_loss += d_loss.item()
            total_phys_loss += p_loss.item()
            total_mae += torch.mean(torch.abs(predictions.float() - y_batch.view_as(predictions))).item()
            
            if (batch_idx + 1) % 20 == 0:
                elapsed_ms = (time.time() - batch_start_time) * 1000
                print(f"      -> Processed {batch_idx + 1}/{total_batches} | Last 20 batches: {elapsed_ms:.0f}ms")
                batch_start_time = time.time() 

        scheduler.step()

        avg_d_loss = total_data_loss / total_batches
        avg_p_loss = total_phys_loss / total_batches
        avg_mae = total_mae / total_batches
        epoch_time = time.time() - epoch_start
        
        print(f"\n>> EPOCH [{epoch+1:03d}/{EPOCHS}] COMPLETED IN {epoch_time:.1f}s")
        print(f"   | MAE: {avg_mae:.6f} | Data Loss: {avg_d_loss:.6f} | Physics Loss: {avg_p_loss:.6f} | LR: {scheduler.get_last_lr()[0]:.2e}")

        if avg_mae < best_loss:
            best_loss = avg_mae
            torch.save(model.state_dict(), MODEL_SAVE_PATH)
            print(f"   [+] New Global Minimum. Weights saved.")
            
        if avg_mae <= TARGET_MAE:
            print(f"\n[!!!] TARGET PRECISION ACHIEVED ({TARGET_MAE} MAE).")
            break

    elapsed = (time.time() - forge_start) / 60
    print(f"\n=== FORGE COMPLETE ===")
    print(f"Total Training Time : {elapsed:.2f} minutes")
    print(f"Peak Precision (MAE): {best_loss:.6f}")

if __name__ == "__main__":
    initiate_neural_forge()