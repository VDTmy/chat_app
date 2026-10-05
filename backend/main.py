from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.auth import router as auth_router
from app.api.v1.conversations import router as conversations_router
from app.api.v1.files import router as files_router
from app.api.v1.friends import router as friends_router
from app.api.v1.messages import router as messages_router
from app.api.v1.users import router as users_router
from app.api.v1.ws import router as ws_router
from app.core.config import settings
from app.kafka.producer import start_producer as kafka_start, stop_producer as kafka_stop
from app.redis.client import close_redis, get_redis
from app.services.file_service import ensure_bucket_exists
from app.websocket.manager import manager


# ---------------------------------------------------------------------------
# Application lifespan — startup & shutdown
# ---------------------------------------------------------------------------
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialise shared resources on startup and clean up on shutdown."""
    # ── Startup ──────────────────────────────────────────────────────────
    # Warm up the Redis client so the first request doesn't pay the cost
    await get_redis()

    # Ensure MinIO bucket exists (non-fatal if MinIO isn't ready)
    try:
        ensure_bucket_exists()
    except Exception as _minio_err:  # noqa: BLE001
        import logging
        logging.getLogger(__name__).warning(
            "MinIO not available at startup (file uploads disabled): %s", _minio_err
        )

    # Start Kafka producer (non-fatal if Kafka isn't ready)
    await kafka_start()

    # Start the background task that relays Redis Pub/Sub messages to local
    # WebSocket connections (enables multi-server broadcasting)
    await manager.start_redis_subscriber()

    yield

    # ── Shutdown ──────────────────────────────────────────────────────────
    await manager.stop_redis_subscriber()
    await kafka_stop()
    await close_redis()


# ---------------------------------------------------------------------------
# FastAPI application
# ---------------------------------------------------------------------------
app = FastAPI(
    title="Real-Time Chat & Streaming Analytics Platform",
    version="1.0.0",
    description=(
        "Real-time chat application with streaming analytics powered by "
        "Apache Kafka and Apache Spark Structured Streaming."
    ),
    lifespan=lifespan,
)

# ---------------------------------------------------------------------------
# CORS – allow all origins during development
# ---------------------------------------------------------------------------
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# Routers
# ---------------------------------------------------------------------------
app.include_router(auth_router)
app.include_router(users_router)
app.include_router(friends_router)
app.include_router(conversations_router)
app.include_router(messages_router)
app.include_router(files_router)
app.include_router(ws_router)

# Analytics router (reads from PostgreSQL analytics tables)
try:
    from app.api.v1.analytics import router as analytics_router
    app.include_router(analytics_router)
except ImportError:
    pass  # Analytics module not yet created


# ---------------------------------------------------------------------------
# Health-check endpoint
# ---------------------------------------------------------------------------
@app.get("/", tags=["health"])
async def health_check():
    return {
        "status": "ok",
        "app": app.title,
        "version": app.version,
    }

