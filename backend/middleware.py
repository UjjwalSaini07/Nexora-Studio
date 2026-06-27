# backend/middleware.py
"""
Lightweight rate-limiting middleware backed by Redis fixed-window counters,
keyed by client IP. Applied globally in main.py. Exempts /v1/healthz so
liveness probes are never throttled.
"""
import time

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

from config import RATE_LIMIT_PER_MINUTE
from logging_config import get_logger

logger = get_logger("nexora.middleware")

EXEMPT_PATHS = {"/v1/healthz", "/", "/docs", "/openapi.json", "/redoc"}


class RateLimitMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        if request.url.path in EXEMPT_PATHS:
            return await call_next(request)

        redis = getattr(request.app.state, "redis", None)
        if redis is None:
            # Store not ready yet (e.g. during startup) — fail open.
            return await call_next(request)

        client_ip = request.client.host if request.client else "unknown"
        bucket_key = f"{client_ip}:{request.url.path}"
        try:
            allowed, count = await redis.rate_limit_hit(bucket_key, window_seconds=60, limit=RATE_LIMIT_PER_MINUTE)
        except Exception as exc:  # pragma: no cover - never let rate limiting crash a request
            logger.error("Rate limit check failed, failing open", extra={"ctx": {"error": str(exc)}})
            return await call_next(request)

        if not allowed:
            logger.warning(
                "Rate limit exceeded",
                extra={"ctx": {"client_ip": client_ip, "path": request.url.path, "count": count}},
            )
            return JSONResponse(
                status_code=429,
                content={"detail": "Rate limit exceeded. Please slow down.", "limit_per_minute": RATE_LIMIT_PER_MINUTE},
            )

        return await call_next(request)


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Logs method, path, status code, and latency for every request."""

    async def dispatch(self, request: Request, call_next):
        start = time.perf_counter()
        response = await call_next(request)
        duration_ms = round((time.perf_counter() - start) * 1000, 2)
        logger.info(
            "request_handled",
            extra={
                "ctx": {
                    "method": request.method,
                    "path": request.url.path,
                    "status_code": response.status_code,
                    "duration_ms": duration_ms,
                }
            },
        )
        return response
