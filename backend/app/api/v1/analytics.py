"""
Analytics API — read-only endpoints for the streaming analytics dashboard.

These endpoints query the PostgreSQL analytics tables that are populated by
Spark Structured Streaming. They provide pre-aggregated metrics.

All analytics data flows through:
    Kafka → Spark → PostgreSQL (analytics tables) → This API → React Dashboard

The API NEVER computes analytics on the fly from OLTP tables.
"""

import logging
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_user
from app.db.session import get_db
from app.models.user import User

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/analytics", tags=["analytics"])


# ---------------------------------------------------------------------------
# GET /analytics/messages-per-minute
# ---------------------------------------------------------------------------
@router.get("/messages-per-minute")
async def get_messages_per_minute(
    limit: int = Query(default=60, ge=1, le=1440, description="Number of windows to return"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Return the most recent message-count windows (newest first).

    Each record represents a 1-minute tumbling window with the total
    number of messages sent during that window.
    """
    result = await db.execute(
        text("""
            SELECT window_start, window_end, message_count
            FROM stream_messages_per_minute
            ORDER BY window_start DESC
            LIMIT :limit
        """),
        {"limit": limit},
    )
    rows = result.fetchall()
    return [
        {
            "window_start": row.window_start.isoformat() if row.window_start else None,
            "window_end": row.window_end.isoformat() if row.window_end else None,
            "message_count": row.message_count,
        }
        for row in rows
    ]


# ---------------------------------------------------------------------------
# GET /analytics/active-users
# ---------------------------------------------------------------------------
@router.get("/active-users")
async def get_active_users(
    limit: int = Query(default=60, ge=1, le=1440, description="Number of windows to return"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Return the most recent active-user-count windows (newest first).

    Each record represents a 1-minute tumbling window with the approximate count of
    DISTINCT users who sent at least one message during that window.
    Note: uses approx_count_distinct (HyperLogLog, ~2% error) — exact count
    distinct is not available in Spark Structured Streaming aggregations.
    """
    result = await db.execute(
        text("""
            SELECT window_start, window_end, active_users
            FROM stream_active_users_per_minute
            ORDER BY window_start DESC
            LIMIT :limit
        """),
        {"limit": limit},
    )
    rows = result.fetchall()
    return [
        {
            "window_start": row.window_start.isoformat() if row.window_start else None,
            "window_end": row.window_end.isoformat() if row.window_end else None,
            "active_users": row.active_users,
        }
        for row in rows
    ]


# ---------------------------------------------------------------------------
# GET /analytics/conversations
# ---------------------------------------------------------------------------
@router.get("/conversations")
async def get_messages_per_conversation(
    minutes: int = Query(default=20, ge=1, le=1440, description="Look-back window in minutes"),
    top: int = Query(default=10, ge=1, le=100, description="Number of top conversations"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Return the most active conversations over the last `minutes` minutes.

    Aggregates SUM(message_count) per conversation_id so the result covers the
    same time range as the messages-per-minute chart (default 20 min).

    The previous implementation returned N raw rows which only covered a few
    minutes at low traffic, making it inconsistent with the other charts.
    """
    result = await db.execute(
        text("""
            SELECT
                conversation_id,
                SUM(message_count)  AS total_messages,
                MIN(window_start)   AS first_seen,
                MAX(window_end)     AS last_seen
            FROM stream_messages_per_conversation
            WHERE window_start >= now() - (make_interval(mins => :minutes))
            GROUP BY conversation_id
            ORDER BY total_messages DESC
            LIMIT :top
        """),
        {"minutes": minutes, "top": top},
    )
    rows = result.fetchall()
    return [
        {
            "conversation_id": row.conversation_id,
            "message_count": row.total_messages,
            "first_seen": row.first_seen.isoformat() if row.first_seen else None,
            "last_seen": row.last_seen.isoformat() if row.last_seen else None,
        }
        for row in rows
    ]
