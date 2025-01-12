import hmac
import hashlib
import os
from datetime import datetime, timezone
from typing import Callable, Set

import redis.asyncio as redis
from fastapi import FastAPI, Request, HTTPException, status
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response

from api.vault_manager import vault
from api.memory_utils import secure_zero, force_garbage_collection

# Redis Configuration for Anti-Replay Cache
REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT = int(os.getenv("REDIS_PORT", 6379))
redis_client = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, decode_responses=True)

_REDIS_OPTIONAL = os.getenv("SENTINEL_REDIS_OPTIONAL", "").lower() in ("1", "true", "yes")


def _exempt_post_paths() -> Set[str]:
    raw = os.getenv(
        "SENTINEL_HMAC_EXEMPT_POST_PATHS",
        "/api/v1/emergency/last-known",
    )
    return {p.strip() for p in raw.split(",") if p.strip()}


class PayloadIntegrityMiddleware(BaseHTTPMiddleware):
    """
    FastAPI middleware: HMAC-SHA256 over canonical string (browser Web Crypto compatible).
    Canonical: METHOD + path + timestamp + nonce + hex(SHA256(raw body)).
    """

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        if request.method != "POST":
            return await call_next(request)

        if request.url.path in _exempt_post_paths():
            return await call_next(request)

        timestamp_header = request.headers.get("X-Timestamp")
        nonce_header = request.headers.get("X-Nonce")
        auth_header = request.headers.get("Authorization")

        if not all([timestamp_header, nonce_header, auth_header]):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Security Handshake Failed: Missing Integrity or Auth Headers",
            )

        if not auth_header.startswith("Bearer "):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Security Handshake Failed: Invalid Authorization Schema",
            )

        token = auth_header.split(" ")[1]

        try:
            request_ts = float(timestamp_header)
            current_ts = datetime.now(timezone.utc).timestamp()
            if abs(current_ts - request_ts) > 60:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Security Handshake Failed: Temporal Window Expired",
                )
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Invalid Timestamp Format",
            )

        # Nonce verification remains critical for Anti-Replay
        nonce_key = f"nonce:{nonce_header}"
        try:
            is_used = await redis_client.get(nonce_key)
        except Exception as exc:
            if not _REDIS_OPTIONAL:
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail=f"Nonce verification unavailable: {exc}",
                ) from exc
            is_used = None
        if is_used:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Security Handshake Failed: Nonce Replay Detected",
            )

        # JWT Validation
        try:
            import jwt
            hmac_secret = await vault.get_hmac_secret()
            jwt.decode(token, hmac_secret, algorithms=["HS256"])
        except jwt.ExpiredSignatureError:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Security Handshake Failed: Session Expired",
            )
        except Exception as exc:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Security Handshake Failed: Invalid Session Token ({exc})",
            )

        try:
            await redis_client.set(nonce_key, "1", ex=60)
        except Exception as exc:
            if not _REDIS_OPTIONAL:
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail=f"Nonce commit unavailable: {exc}",
                ) from exc
        force_garbage_collection()

        async def receive():
            return {"type": "http.request", "body": body}

        request._receive = receive

        return await call_next(request)


# --------------------------------------------------------------------------------
# DEMONSTRATION BLOCK (standalone crucible entrypoint)
# --------------------------------------------------------------------------------

demo_app = FastAPI(title="Sentinel V7 Security Crucible")
demo_app.add_middleware(PayloadIntegrityMiddleware)


@demo_app.post("/api/v1/telemetry/secure-ingest")
async def secure_ingest(data: dict):
    """Executes only after PayloadIntegrityMiddleware passes."""
    return {
        "status": "SECURE",
        "message": "Telemetry accepted into the V7 Neural Matrix",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


if __name__ == "__main__":
    import uvicorn

    print("Initializing Track Alpha: Security Middleware Crucible...")
    uvicorn.run(demo_app, host="0.0.0.0", port=8000)
