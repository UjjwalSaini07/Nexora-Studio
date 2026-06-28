from fastapi import Depends, Header, HTTPException, Request, status

from config import API_AUTH_TOKEN, ENABLE_AUTH
from storage.redis_store import RedisStore
from storage.mongo_store import MongoStore


async def get_redis(request: Request) -> RedisStore:
    return request.app.state.redis


async def get_mongo(request: Request) -> MongoStore:
    return request.app.state.mongo


async def verify_auth(authorization: str = Header(default="")) -> None:
    if not ENABLE_AUTH:
        return
    expected = f"Bearer {API_AUTH_TOKEN}"
    if not API_AUTH_TOKEN or authorization != expected:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or missing credentials")
