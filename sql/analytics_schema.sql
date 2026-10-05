-- ============================================================================
-- Analytics Schema for Streaming Pipeline
-- ============================================================================
-- These tables store pre-aggregated metrics computed by Spark Structured
-- Streaming. They are SEPARATE from the OLTP chat tables.
--
-- OLTP tables: users, messages, conversations, conversation_members, ...
-- Analytics tables: stream_messages_per_minute, stream_active_users_per_minute,
--                   stream_messages_per_conversation
--
-- All analytics tables use the "stream_" prefix to clearly distinguish them
-- from operational data.
-- ============================================================================

-- ---------------------------------------------------------------------------
-- Metric 1: Messages Per Minute
-- ---------------------------------------------------------------------------
-- Counts the total number of messages sent within each 1-minute tumbling window.
-- Written by Spark foreachBatch via JDBC.
CREATE TABLE IF NOT EXISTS stream_messages_per_minute (
    window_start    TIMESTAMP WITH TIME ZONE NOT NULL,
    window_end      TIMESTAMP WITH TIME ZONE NOT NULL,
    message_count   BIGINT NOT NULL DEFAULT 0,
    PRIMARY KEY (window_start, window_end)
);

-- Index for dashboard queries (ORDER BY window_start DESC LIMIT N)
CREATE INDEX IF NOT EXISTS idx_stream_msg_per_min_start
    ON stream_messages_per_minute (window_start DESC);


-- ---------------------------------------------------------------------------
-- Metric 2: Active Users Per Minute
-- ---------------------------------------------------------------------------
-- Counts the number of DISTINCT users who sent at least one message within
-- each 1-minute tumbling window.
-- Note: This is NOT simply count(messages). Spark uses countDistinct(user_id).
CREATE TABLE IF NOT EXISTS stream_active_users_per_minute (
    window_start    TIMESTAMP WITH TIME ZONE NOT NULL,
    window_end      TIMESTAMP WITH TIME ZONE NOT NULL,
    active_users    BIGINT NOT NULL DEFAULT 0,
    PRIMARY KEY (window_start, window_end)
);

CREATE INDEX IF NOT EXISTS idx_stream_active_users_start
    ON stream_active_users_per_minute (window_start DESC);


-- ---------------------------------------------------------------------------
-- Metric 3: Messages Per Conversation Per Minute
-- ---------------------------------------------------------------------------
-- Counts messages grouped by conversation_id within each 1-minute window.
-- Allows the dashboard to show which conversations are most active.
CREATE TABLE IF NOT EXISTS stream_messages_per_conversation (
    window_start        TIMESTAMP WITH TIME ZONE NOT NULL,
    window_end          TIMESTAMP WITH TIME ZONE NOT NULL,
    conversation_id     VARCHAR(36) NOT NULL,
    message_count       BIGINT NOT NULL DEFAULT 0,
    PRIMARY KEY (window_start, window_end, conversation_id)
);

CREATE INDEX IF NOT EXISTS idx_stream_msg_per_conv_start
    ON stream_messages_per_conversation (window_start DESC);

CREATE INDEX IF NOT EXISTS idx_stream_msg_per_conv_conv
    ON stream_messages_per_conversation (conversation_id);
