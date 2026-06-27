# backend/main.py
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from logging_config import configure_logging, get_logger
from storage.redis_store import RedisStore
from storage.mongo_store import MongoStore
from routers import healthz, metadata, context, tick, reply, dashboard, teardown
from dataset.loader import load_dataset_to_mongo
from middleware import RateLimitMiddleware, RequestLoggingMiddleware
from config import MONGO_URI, REDIS_URL

configure_logging()
logger = get_logger("nexora.main")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # ── Startup ──────────────────────────────────────────────────────────
    logger.info("NEXORA bot starting up...")
    app.state.redis = RedisStore(REDIS_URL)
    app.state.mongo = MongoStore(MONGO_URI)

    try:
        await app.state.mongo.ensure_indexes()
    except Exception as exc:
        logger.error("Failed to ensure Mongo indexes (continuing anyway)", extra={"ctx": {"error": str(exc)}})

    try:
        await load_dataset_to_mongo(app.state.mongo, app.state.redis)
        from dataset.demo_generator import ensure_demo_data
        await ensure_demo_data(app.state.mongo, app.state.redis)
    except Exception as exc:
        logger.error("Dataset preload or demo seeding failed (continuing anyway)", extra={"ctx": {"error": str(exc)}})

    try:
        await app.state.redis.get_start_time()
    except Exception as exc:
        logger.error(
            "Failed to initialize Redis start_time at boot (continuing anyway; "
            "healthz will report redis_connected=False until Redis is reachable)",
            extra={"ctx": {"error": str(exc)}},
        )
    logger.info("NEXORA bot startup complete.")

    yield

    # ── Shutdown ─────────────────────────────────────────────────────────
    logger.info("NEXORA bot shutting down...")
    await app.state.redis.close()
    app.state.mongo.close()


app = FastAPI(
    title="NEXORA Bot",
    description="magicpin AI Challenge — NEXORA merchant engagement engine",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS: the dashboard (Next.js, typically on a different origin/port) needs
# to call this API directly from the browser. The judge harness calls
# server-to-server and is unaffected by CORS. Restrict via env var in
# production rather than leaving this wide open.
_cors_origins = os.getenv("CORS_ALLOW_ORIGINS", "*")
allow_origins = ["*"] if _cors_origins == "*" else [o.strip() for o in _cors_origins.split(",")]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allow_origins,
    allow_credentials=allow_origins != ["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(RateLimitMiddleware)
app.add_middleware(RequestLoggingMiddleware)


def _sanitize_validation_errors(errors: list) -> list:
    """
    Pydantic's exc.errors() can include a 'ctx' dict containing the raw
    exception object that triggered a custom @field_validator ValueError
    (e.g. ctx={'error': ValueError(...)}). That's not JSON-serializable and
    will crash json.dumps()/JSONResponse. Strip it down to plain strings.
    """
    sanitized = []
    for err in errors:
        clean = {k: v for k, v in err.items() if k != "ctx"}
        if "ctx" in err and isinstance(err["ctx"], dict):
            clean["ctx"] = {k: str(v) for k, v in err["ctx"].items()}
        sanitized.append(clean)
    return sanitized


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    safe_errors = _sanitize_validation_errors(exc.errors())
    logger.warning(
        "Request validation failed",
        extra={"ctx": {"path": request.url.path, "errors": safe_errors}},
    )
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={"accepted": False, "reason": "validation_error", "details": safe_errors},
    )


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    logger.error(
        "Unhandled exception",
        extra={"ctx": {"path": request.url.path, "error": str(exc)}},
        exc_info=True,
    )
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"accepted": False, "reason": "internal_error", "details": "An unexpected error occurred."},
    )


@app.get("/")
async def root():
    return {"service": "NEXORA Bot", "status": "running", "docs": "/docs"}


for r in [healthz.router, metadata.router, context.router, tick.router, reply.router, dashboard.router, teardown.router]:
    app.include_router(r)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8080, reload=False)
