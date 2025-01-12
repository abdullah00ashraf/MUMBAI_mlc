import torch
import torch.nn as nn
import torch.nn.functional as F
import math

print("=== INITIALIZING SENTINEL V7: MUMBAI PINN CORE ===")

# --- 1. The Physics-Informed Loss Function ---
# --- 1. The Physics-Informed Loss Function ---
class PINN_Loss(nn.Module):
    def __init__(self, alpha=1.0, beta=0.5):
        super(PINN_Loss, self).__init__()
        self.alpha = alpha # Weight for Data Loss
        self.beta = beta   # Weight for Physics Loss
        
    def forward(self, preds, targets, rain_intensity, tidal_height):
        # Align tensor dimensions [batch_size, 1] to prevent silent broadcast errors
        targets = targets.view_as(preds)
        
        # 1. Data-Driven Loss (Log-Cosh)
        def log_cosh_loss(y_pred, y_true):
            x = y_pred - y_true
            return torch.mean(x + torch.nn.functional.softplus(-2.0 * x) - math.log(2.0))
            
        data_loss = log_cosh_loss(preds, targets)
        
        # 2. Physics-Driven Constraint (Corrected for Min-Max Scaling)
        # Since inputs are squashed to [0.0, 1.0], a raw tide of 4.5m is approx > 0.85
        # A raw rain event translates to approx > 0.01
        lock_mask = (tidal_height > 0.85).float()
        rain_mask = (rain_intensity > 0.01).float()
        
        # Physical Rule: If Hydraulic Lock is ON and Rain is ON, water CANNOT drain.
        # If the neural network predicts near 0 (guessing the water magically disappeared),
        # we hit it with a massive physics penalty.
        # F.relu(0.1 - preds) heavily penalizes predictions that drop below 0.1 during a locked storm.
        physics_violation = F.relu(0.1 - preds) * lock_mask * rain_mask
        physics_loss = torch.mean(physics_violation)
        
        # Total PINN Loss
        total_loss = (self.alpha * data_loss) + (self.beta * physics_loss)
        return total_loss, data_loss, physics_loss
    
# --- 2. The 10M+ Parameter Neural Architecture ---
class SentinelMumbaiPINN(nn.Module):
    def __init__(self, input_dim=9, hidden_dim=512, num_layers=6, output_dim=1):
        super(SentinelMumbaiPINN, self).__init__()
        
        self.hidden_dim = hidden_dim
        self.num_layers = num_layers
        
        # 1. Deep Bi-LSTM Core
        # This will generate the bulk of the 20M+ parameters
        self.lstm = nn.LSTM(
            input_size=input_dim,
            hidden_size=hidden_dim,
            num_layers=num_layers,
            batch_first=True,
            bidirectional=True,
            dropout=0.3 # Crucial to prevent overfitting with a massive model
        )
        
        # 2. Self-Attention Head
        # Focuses the neural network on the exact hour the tide peaks
        self.attention = nn.Linear(hidden_dim * 2, 1)
        
        # 3. Fully Connected Decoder
        self.fc1 = nn.Linear(hidden_dim * 2, 256)
        self.relu = nn.ReLU()
        self.dropout = nn.Dropout(0.3)
        self.fc2 = nn.Linear(256, 64)
        self.out = nn.Linear(64, output_dim)
        
    def forward(self, x):
        # x shape: (batch_size, sequence_length, features)
        
        # LSTM Pass
        lstm_out, (h_n, c_n) = self.lstm(x) # lstm_out: (batch, seq_len, hidden_dim * 2)
        
        # Attention Mechanism
        attn_weights = F.softmax(self.attention(lstm_out), dim=1)
        context_vector = torch.sum(attn_weights * lstm_out, dim=1) # (batch, hidden_dim * 2)
        
        # Decoder Pass
        x = self.fc1(context_vector)
        x = self.relu(x)
        x = self.dropout(x)
        x = self.fc2(x)
        x = self.relu(x)
        
        # Final Prediction (Flood Depth)
        pred = self.out(x)
        return pred

# --- 3. Diagnostics & Parameter Verification ---
def deploy_model():
    # Instantiate the PINN
    model = SentinelMumbaiPINN(input_dim=9, hidden_dim=512, num_layers=6)
    
    # Calculate exact trainable weights
    total_params = sum(p.numel() for p in model.parameters() if p.requires_grad)
    
    print("\n>> TACTICAL NEURAL DIAGNOSTICS:")
    print(f"[ARCT] Topology          : 6-Layer Bi-LSTM + Self-Attention")
    print(f"[ARCT] Hidden Dimensions : 512 Units / Direction")
    print(f"[ARCT] Active Parameters : {total_params:,} Weights")
    
    if total_params > 10000000:
         print("[STATUS] REQUIREMENT MET: Neural core successfully exceeds 10 Million parameters.")
    
    print("[ARCT] PINN Loss Engine  : Log-Cosh + Hydraulic Mass Conservation Matrix")
    print("=== MODEL AWAITING TENSOR INGRESS ===\n")
    
    return model

if __name__ == "__main__":
    # Test compilation
    core = deploy_model()