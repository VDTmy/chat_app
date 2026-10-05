"""
Kafka Producer — async producer for publishing chat events to Kafka.

This module encapsulates ALL Kafka logic in one place.
No Kafka code should be scattered across other modules.

Architecture:
    FastAPI lifespan
        │
        ├── start_producer()   (on startup)
        │
        └── stop_producer()    (on shutdown)

    Event handlers (after DB commit)
        │
        └── publish_chat_event()  (fire-and-forget)

Design Decisions:
    - Uses aiokafka (async) to integrate naturally with FastAPI's async event loop.
    - Producer is a module-level singleton, started/stopped by the app lifespan.
    - publish_chat_event() is fire-and-forget: if Kafka is down, the error is
      logged but the chat message (already committed to PostgreSQL) is NOT lost.
    - Events are published with conversation_id as the Kafka key, ensuring all
      messages from the same conversation land on the same partition (important
      for per-conversation analytics ordering).

Trade-offs:
    - If Kafka is temporarily unavailable, analytics events are lost (acceptable
      for near-real-time analytics — the chat data is safe in PostgreSQL).
    - We do NOT use transactions between PostgreSQL and Kafka (no 2PC) because
      the analytics pipeline is a secondary, non-critical data flow.
"""

import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Optional

from app.core.config import settings

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Module-level singleton
# ---------------------------------------------------------------------------
_producer: Optional[object] = None  # AIOKafkaProducer (typed loosely to avoid import-time errors)


async def start_producer() -> None:
    """Initialise and start the Kafka producer.

    Called once during FastAPI lifespan startup.
    If Kafka is not available, logs a warning but does NOT crash the app.
    """
    global _producer

    try:
        from aiokafka import AIOKafkaProducer  # noqa: WPS433

        _producer = AIOKafkaProducer(
            bootstrap_servers=settings.KAFKA_BOOTSTRAP_SERVERS,
            # Serialise values as UTF-8 JSON strings
            value_serializer=lambda v: json.dumps(v, default=str).encode("utf-8"),
            # Serialise keys as UTF-8 strings (used for partition routing)
            key_serializer=lambda k: k.encode("utf-8") if k else None,
            # Idempotent delivery: exactly-once per producer session.
            # Requires acks="all" and retries > 0 (set automatically by aiokafka).
            enable_idempotence=True,
        )
        await _producer.start()
        logger.info(
            "Kafka producer started — bootstrap_servers=%s, topic=%s",
            settings.KAFKA_BOOTSTRAP_SERVERS,
            settings.KAFKA_CHAT_TOPIC,
        )
    except Exception as exc:
        logger.warning(
            "Failed to start Kafka producer (analytics disabled): %s", exc
        )
        _producer = None


async def stop_producer() -> None:
    """Flush pending messages and shut down the Kafka producer.

    Called once during FastAPI lifespan shutdown.
    """
    global _producer

    if _producer is not None:
        try:
            await _producer.stop()
            logger.info("Kafka producer stopped")
        except Exception as exc:
            logger.warning("Error stopping Kafka producer: %s", exc)
        finally:
            _producer = None


async def publish_chat_event(
    *,
    event_type: str,
    message_id: uuid.UUID,
    user_id: uuid.UUID,
    conversation_id: uuid.UUID,
    message_type: str,
    timestamp: datetime,
) -> None:
    """Publish a chat event to the Kafka topic.

    This function is designed to be called AFTER a successful PostgreSQL commit.
    It is fire-and-forget: errors are logged but never propagated to the caller,
    ensuring that a Kafka failure does not break the chat functionality.

    Parameters
    ----------
    event_type : str
        Type of event, e.g. "message_sent".
    message_id : UUID
        The database ID of the message.
    user_id : UUID
        The sender's user ID.
    conversation_id : UUID
        The conversation the message belongs to.
    message_type : str
        Content type: "text", "image", or "file".
    timestamp : datetime
        The event time (message created_at). Used as event time in Spark.
    """
    if _producer is None:
        logger.debug("Kafka producer not available — skipping event publish")
        return

    event = {
        "event_type": event_type,
        "message_id": str(message_id),
        "user_id": str(user_id),
        "conversation_id": str(conversation_id),
        "message_type": message_type,
        "timestamp": timestamp.isoformat() if isinstance(timestamp, datetime) else str(timestamp),
    }

    try:
        # Fire-and-forget with a 5-second timeout so a slow/unavailable Kafka
        # broker does not block the request handler indefinitely.
        import asyncio
        await asyncio.wait_for(
            _producer.send(
                topic=settings.KAFKA_CHAT_TOPIC,
                key=str(conversation_id),
                value=event,
            ),
            timeout=5.0,
        )
        logger.debug("Kafka event published: %s", event)
    except Exception as exc:
        # CRITICAL DESIGN DECISION:
        # We catch ALL exceptions here and only log them.
        # The chat message is already committed to PostgreSQL — it is SAFE.
        # Losing an analytics event is acceptable; losing a chat message is not.
        logger.error(
            "Failed to publish Kafka event (message_id=%s): %s",
            message_id,
            exc,
        )
