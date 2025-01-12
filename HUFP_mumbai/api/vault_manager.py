import os
import httpx
import asyncio
from typing import Optional, Dict

class VaultManager:
    """
    Handles secure secret retrieval from HashiCorp Vault for the Sentinel V7 Matrix.
    Implements the 'Envelope Encryption' foundation for Data at Rest and HMAC keys.
    Includes a Development Fallback to prevent system-wide ignition failure.
    """
    
    def __init__(self):
        self.vault_url = os.getenv("VAULT_ADDR", "http://127.0.0.1:8200").rstrip("/")
        # Empty default: do not contact Vault until VAULT_TOKEN is set (avoids accidental dev root token use).
        self.vault_token = os.getenv("VAULT_TOKEN", "").strip()
        self.client = httpx.AsyncClient(base_url=self.vault_url, timeout=2.0)

    async def get_secret(self, path: str, key: str) -> Optional[str]:
        """
        Fetches a specific key from a Vault KV (Version 2) engine.
        """
        if not self.vault_token:
            return None
        try:
            endpoint = f"/v1/secret/data/{path}"
            headers = {"X-Vault-Token": self.vault_token}

            response = await self.client.get(endpoint, headers=headers)
            if response.status_code == 200:
                data = response.json()
                # KV V2 structure is nested: data -> data -> {key}
                return data.get("data", {}).get("data", {}).get(key)
            else:
                return None
        except (httpx.ConnectError, httpx.ConnectTimeout):
            # Silently handle connection errors to allow the caller to use fallbacks
            return None
        except Exception as e:
            print(f"Vault Manager Internal Error: {e}")
            return None

    async def get_hmac_secret(self) -> bytes:
        """
        Retrieves the HMAC-SHA256 shared secret (matches browser Web Crypto).
        Falls back to environment if Vault is unreachable or token unset.
        """
        secret = await self.get_secret("sentinel/security", "hmac_key")
        if secret:
            return secret.encode()
        
        # Fallback for Development/Ignition
        fallback = os.getenv(
            "V7_SECURITY_SECRET",
            "quantum_shield_dummy_secret_2026",
        )
        print("--- WARNING: Using HMAC Security Fallback (set VAULT_TOKEN or V7_SECURITY_SECRET) ---")
        return fallback.encode()

    async def get_encryption_key(self) -> bytes:
        """
        Retrieves the AES-256-GCM key for Envelope Encryption.
        Crucial for decrypting sentinel_mumbai_v1_cloud.pt during startup.
        """
        key = await self.get_secret("sentinel/encryption", "aes_key")
        if key:
            return key.encode()
        
        # Fallback for Development/Ignition
        fallback = os.getenv("V7_ENCRYPTION_KEY", "32_byte_dummy_key_for_aes_256_!!")
        print("--- WARNING: Vault Unreachable. Using LOCAL_ENCRYPTION_KEY Fallback ---")
        return fallback.encode()

    async def close(self):
        await self.client.aclose()

# Singleton instance
vault = VaultManager()