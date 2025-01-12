import os
import glob
import pandas as pd
import numpy as np
import tensorflow as tf
from tensorflow.keras import layers, models, optimizers
from tensorflow.keras.callbacks import ModelCheckpoint, EarlyStopping, ReduceLROnPlateau
import pyarrow.parquet as pq

# --- 1. HARDWARE ACCELERATION (Tesla T4 Optimization) ---
# Enable Mixed Precision to utilize Tensor Cores on the T4 GPU
policy = tf.keras.mixed_precision.Policy('mixed_float16')
tf.keras.mixed_precision.set_global_policy(policy)

# --- 2. CONFIGURATION ---
# Pointing to the directory of partitioned Parquet files
DATA_DIR = "/content/drive/MyDrive/HUFP_mumbai/fused_dataset"
MODEL_SAVE_DIR = "/content/drive/MyDrive/HUFP_mumbai/brain"
os.makedirs(MODEL_SAVE_DIR, exist_ok=True)

BATCH_SIZE = 2048 # High batch size for T4 VRAM efficiency
WINDOW_SIZE = 24  # 24-hour lookback memory
FEATURES = 8      # [long, lat, rainfall, tide, soil, elev, slope, landcover]

# --- 3. HIGH-PERFORMANCE DATA PIPELINE (Streaming Parquet) ---
def get_dataset(parquet_dir):
    def generator():
        # Find all yearly parquet files in the directory
        parquet_files = sorted(glob.glob(os.path.join(parquet_dir, "*.parquet")))
        
        for file_path in parquet_files:
            print(f"\n📡 Streaming {os.path.basename(file_path)} into Neural Network...")
            pf = pq.ParquetFile(file_path)
            
            # Stream in chunks of 50,000 rows so Colab RAM never overflows
            for batch in pf.iter_batches(batch_size=50000):
                df = batch.to_pandas()
                
                # X features: longitude to landcover (indices 1 through 8)
                X = df.iloc[:, 1:-1].values.astype('float32') 
                # y target: is_flooded_2017 (last column)
                y = df.iloc[:, -1].values.astype('float32')  
                
                # Reshape for Sequence processing [Samples, Window, Features]
                for i in range(len(X) - WINDOW_SIZE):
                    yield X[i:i+WINDOW_SIZE], y[i+WINDOW_SIZE]

    dataset = tf.data.Dataset.from_generator(
        generator,
        output_signature=(
            tf.TensorSpec(shape=(WINDOW_SIZE, FEATURES), dtype=tf.float32),
            tf.TensorSpec(shape=(), dtype=tf.float32)
        )
    )
    # Shuffle and prefetch to keep the GPU fed with data constantly
    return dataset.shuffle(5000).batch(BATCH_SIZE).prefetch(tf.data.AUTOTUNE)

# --- 4. THE HYBRID PINN + ATTENTION MODEL ---
class SentinelPhysicsModel(tf.keras.Model):
    def __init__(self):
        super(SentinelPhysicsModel, self).__init__()
        # Part A: Temporal Encoder
        self.lstm_1 = layers.Bidirectional(layers.LSTM(128, return_sequences=True))
        self.lstm_2 = layers.Bidirectional(layers.LSTM(64, return_sequences=True))
        
        # Part B: Attention Mechanism
        self.attention = layers.Attention()
        
        # Part C: Latent Mapping (SiLU activation)
        self.dense_1 = layers.Dense(128, activation='silu')
        self.batch_norm = layers.BatchNormalization()
        self.dropout = layers.Dropout(0.3)
        self.dense_2 = layers.Dense(64, activation='relu')
        
        # Output: Sigmoid Risk (Must be float32 for numerical stability)
        self.risk_head = layers.Dense(1, activation='sigmoid', dtype='float32')

    def call(self, inputs):
        x = self.lstm_1(inputs)
        x = self.lstm_2(x)
        
        # Apply Attention over the 24-hour sequence
        query_value_attention_seq = self.attention([x, x])
        x = layers.GlobalAveragePooling1D()(query_value_attention_seq)
        
        x = self.dense_1(x)
        x = self.batch_norm(x)
        x = self.dropout(x)
        x = self.dense_2(x)
        return self.risk_head(x)

    @tf.function(jit_compile=True) # XLA JIT Compilation for T4 acceleration
    def train_step(self, data):
        X, y_true = data
        
        with tf.GradientTape(persistent=True) as tape:
            tape.watch(X)
            y_pred = self(X, training=True)
            
            # 1. Data-Driven Loss (BCE)
            loss_data = tf.keras.losses.binary_crossentropy(y_true, y_pred)
            
            # 2. Physics-Informed Residual (Continuity Equation)
            # dy_dt = derivative of risk with respect to inputs
            dy_dt = tape.gradient(y_pred, X)[:, -1, 2] # Index 2 is rainfall
            
            rainfall = X[:, -1, 2]
            is_concrete = tf.cast(tf.equal(X[:, -1, 7], 80), tf.float32) # Index 7 is landcover
            
            # Physics Logic: Infiltration is zero in urban concrete
            infiltration = 0.5 * (1.0 - is_concrete)
            pde_residual = dy_dt - (rainfall - infiltration)
            loss_physics = tf.reduce_mean(tf.square(pde_residual))
            
            # Total Fused Loss
            total_loss = loss_data + (0.01 * loss_physics)

        # Gradient Optimization
        gradients = tape.gradient(total_loss, self.trainable_variables)
        self.optimizer.apply_gradients(zip(gradients, self.trainable_variables))
        
        return {"loss": total_loss, "bce": loss_data, "pde": loss_physics}

# --- 5. TRAINING SESSION ---
def run_colab_training():
    model = SentinelPhysicsModel()
    
    # Advanced AdamW Optimizer with Weight Decay
    optimizer = optimizers.AdamW(learning_rate=0.0007, weight_decay=0.004)
    model.compile(optimizer=optimizer)
    
    callbacks = [
        ModelCheckpoint(os.path.join(MODEL_SAVE_DIR, "sentinel_v7_best.keras"), 
                        save_best_only=True, monitor='loss'),
        EarlyStopping(monitor='loss', patience=15, restore_best_weights=True),
        ReduceLROnPlateau(monitor='loss', factor=0.5, patience=5)
    ]
    
    print("🚀 Initializing Sentinel HUFP V7 PINN on Tesla T4...")
    dataset = get_dataset(DATA_DIR)
    
    model.fit(
        dataset,
        steps_per_epoch=4000, # Define steps since generator is technically infinite/unknown length
        epochs=100,
        callbacks=callbacks
    )

if __name__ == "__main__":
    run_colab_training()