import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, status, HTTPException
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from logging_config import configure_logging, get_logger
from storage.redis_store import RedisStore
from storage.mongo_store import MongoStore
from routers import healthz, metadata, context, tick, reply, dashboard, teardown, demo, explain
from dataset.loader import load_dataset_to_mongo
from middleware import RateLimitMiddleware, RequestLoggingMiddleware, PayloadSizeMiddleware
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
app.add_middleware(PayloadSizeMiddleware)


def _sanitize_validation_errors(errors: list) -> list:
    sanitized = []
    for err in errors:
        clean = {k: v for k, v in err.items() if k != "ctx"}
        if "ctx" in err and isinstance(err["ctx"], dict):
            clean["ctx"] = {k: str(v) for k, v in err["ctx"].items()}
        sanitized.append(clean)
    return sanitized


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    errors = exc.errors()
    # Check if this is a JSON decode error / malformed JSON
    is_malformed_json = any(
        err.get("type") in {"json_invalid", "value_error.jsondecode"} 
        or "json decode error" in str(err.get("msg", "")).lower()
        for err in errors
    )
    
    if is_malformed_json:
        logger.warning("Request body contains malformed JSON", extra={"ctx": {"path": request.url.path}})
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={
                "success": False,
                "accepted": False,
                "reason": "invalid_json",
                "error": {
                    "code": "INVALID_JSON",
                    "message": "Request body contains malformed JSON."
                }
            }
        )

    safe_errors = _sanitize_validation_errors(errors)
    logger.warning(
        "Request validation failed",
        extra={"ctx": {"path": request.url.path, "errors": safe_errors}},
    )
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "success": False,
            "accepted": False,
            "reason": "validation_error",
            "details": safe_errors,
            "error": {
                "code": "VALIDATION_ERROR",
                "message": "Request validation failed.",
                "details": safe_errors
            }
        },
    )


@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request: Request, exc: StarletteHTTPException):
    code_map = {
        400: "BAD_REQUEST",
        401: "UNAUTHORIZED",
        403: "FORBIDDEN",
        404: "NOT_FOUND",
        405: "METHOD_NOT_ALLOWED",
        413: "PAYLOAD_TOO_LARGE",
        422: "UNPROCESSABLE_ENTITY",
        429: "RATE_LIMIT_EXCEEDED",
    }
    code = code_map.get(exc.status_code, "HTTP_ERROR")

    accepted_val = False
    reason_val = "error"
    details_val = None
    message_val = str(exc.detail)

    if isinstance(exc.detail, dict):
        accepted_val = exc.detail.get("accepted", False)
        reason_val = exc.detail.get("reason", "error")
        details_val = exc.detail.get("details")
        message_val = exc.detail.get("message", exc.detail.get("reason", message_val))
        
        if "error" in exc.detail:
            resp_content = dict(exc.detail)
            if "success" not in resp_content:
                resp_content["success"] = False
            return JSONResponse(status_code=exc.status_code, content=resp_content)

    return JSONResponse(
        status_code=exc.status_code,
        content={
            "success": False,
            "accepted": accepted_val,
            "reason": reason_val,
            "details": details_val,
            "error": {
                "code": code,
                "message": message_val,
                "details": details_val
            }
        }
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
        content={
            "success": False,
            "accepted": False,
            "reason": "internal_error",
            "details": "An unexpected error occurred.",
            "error": {
                "code": "INTERNAL_ERROR",
                "message": "An unexpected error occurred."
            }
        },
    )


@app.get("/")
async def root():
    from config import BOT_VERSION
    return {
        "service": "NEXORA Bot Engine",
        "status": "active",
        "version": BOT_VERSION,
        "environment": os.getenv("ENVIRONMENT", "production"),
        "documentation": "/docs",
        "endpoints": {
            "health": "/v1/healthz",
            "metadata": "/v1/metadata",
            "context_ingestion": "/v1/context",
            "proactive_tick": "/v1/tick",
            "conversational_reply": "/v1/reply",
        },
        "developer": {
            "name": "Ujjwal Saini",
            "role": "Lead Architect",
            "portfolio": "https://ujjwalsaini.vercel.app",
        }
    }


for r in [healthz.router, metadata.router, context.router, tick.router, reply.router, dashboard.router, teardown.router, demo.router, explain.router]:
    app.include_router(r)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8080, reload=False)
