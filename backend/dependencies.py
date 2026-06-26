# backend/dependencies.py
"""
Shared FastAPI dependencies: store singletons + optional bearer-token auth.

Stores are created once at process startup (see main.py's lifespan) and
attached to `app.state`. Routers pull them via Depends(get_redis) /
Depends(get_mongo) so they're easy to override in tests (FastAPI's
`app.dependency_overrides`).
"""
from fastapi import Depends, Header, HTTPException, Request, status

from config import API_AUTH_TOKEN, ENABLE_AUTH
from storage.redis_store import RedisStore
from storage.mongo_store import MongoStore


async def get_redis(request: Request) -> RedisStore:
    return request.app.state.redis


async def get_mongo(request: Request) -> MongoStore:
    return request.app.state.mongo


async def verify_auth(authorization: str = Header(default="")) -> None:
    """
    Optional shared-secret auth gate for inbound judge-harness calls.
    Disabled by default (ENABLE_AUTH=false) since the judge harness is not
    guaranteed to send an Authorization header; enable it explicitly via env
    var if you want to lock down the publicly-exposed bot URL.
    """
    if not ENABLE_AUTH:
        return
    expected = f"Bearer {API_AUTH_TOKEN}"
    if not API_AUTH_TOKEN or authorization != expected:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or missing credentials")
