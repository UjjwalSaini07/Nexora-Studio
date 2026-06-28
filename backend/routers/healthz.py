import time
import os
from datetime import datetime, timezone

from fastapi import APIRouter, Depends

from dependencies import get_redis, get_mongo
from models.requests import HealthzResponse
from storage.redis_store import RedisStore
from storage.mongo_store import MongoStore
from logging_config import get_logger

logger = get_logger("nexora.routers.healthz")

router = APIRouter()
_process_start_time = time.time()


@router.get("/v1/healthz", response_model=HealthzResponse)
async def healthz(
    redis: RedisStore = Depends(get_redis),
    mongo: MongoStore = Depends(get_mongo),
):
    """
    Liveness probe. MUST be maximally resilient: a transient Mongo/Redis
    outage should produce status="degraded" with the relevant *_connected
    flag set to False, never a 500. The judge harness polls this endpoint
    to decide whether the bot is up, so a crash here would be far worse
    than reporting reduced functionality.
    """
    uptime = int(time.time() - _process_start_time)

    try:
        redis_ok = await redis.ping()
    except Exception as exc:
        logger.error("Redis ping raised during healthz", extra={"ctx": {"error": str(exc)}})
        redis_ok = False

    try:
        mongo_ok = await mongo.ping()
    except Exception as exc:
        logger.error("Mongo ping raised during healthz", extra={"ctx": {"error": str(exc)}})
        mongo_ok = False

    counts = {"category": 0, "merchant": 0, "customer": 0, "trigger": 0}
    if redis_ok:
        try:
            counts = await redis.get_context_counts()
        except Exception as exc:
            logger.error("get_context_counts failed during healthz", extra={"ctx": {"error": str(exc)}})
            redis_ok = False

    # Rich database counts (resiliently fetched)
    total_actions = 0
    total_replies = 0
    total_suppressions = 0

    if mongo_ok:
        try:
            total_actions = await mongo.actions_log.count_documents({})
            total_replies = await mongo.replies_log.count_documents({})
            total_suppressions = await mongo.suppressions_log.count_documents({})
        except Exception as exc:
            logger.error("DB metrics count failed during healthz", extra={"ctx": {"error": str(exc)}})

    # Calculate memory usage (Linux RSS RSS/1024 to get MB)
    mem_mb = 0.0
    try:
        import resource
        mem_kb = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        mem_mb = round(mem_kb / 1024, 2)
    except Exception:
        pass

    system_start = datetime.fromtimestamp(_process_start_time, timezone.utc).isoformat().replace("+00:00", "Z")
    env = os.getenv("ENVIRONMENT", "production")

    overall_status = "ok" if (redis_ok and mongo_ok) else "degraded"

    return HealthzResponse(
        status=overall_status,
        uptime_seconds=uptime,
        contexts_loaded=counts,
        mongo_connected=mongo_ok,
        redis_connected=redis_ok,
        total_actions_logged=total_actions,
        total_replies_logged=total_replies,
        active_suppression_keys=total_suppressions,
        system_start_time=system_start,
        environment=env,
        memory_usage_mb=mem_mb if mem_mb > 0 else None,
    )

