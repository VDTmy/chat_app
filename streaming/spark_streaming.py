"""
Apache Spark Structured Streaming Job.
Real-Time Chat & Streaming Analytics Platform.

Architecture:
    Kafka ("chat-events")
            │
            ▼
    Spark Structured Streaming
            │
            ├─ Watermark: 30 seconds (handles late-arriving events)
            ├─ Tumbling Window: 1 minute
            │
            ├─ Stream 1: Messages Per Minute (count)
            ├─ Stream 2: Active Users Per Minute (approx_count_distinct user_id)
            └─ Stream 3: Messages Per Conversation (count grouped by conversation_id)
            │
            ▼
    PostgreSQL Analytics Tables (via foreachBatch UPSERT)
            ├─ stream_messages_per_minute
            ├─ stream_active_users_per_minute
            └─ stream_messages_per_conversation

Timezone note:
    PySpark collect() returns naive datetime objects in the *local machine* timezone.
    PostgreSQL (Docker default) assumes UTC for TIMESTAMP WITHOUT TIME ZONE columns,
    but our schema uses TIMESTAMP WITH TIME ZONE — so psycopg2 must hand off an
    aware UTC datetime. We convert every window boundary via .astimezone(timezone.utc).

Idempotency note:
    dropDuplicates(["message_id"]) runs per micro-batch to guard against
    at-least-once Kafka delivery producing duplicate events in one batch.
    The producer uses enable.idempotence=True + acks="all" for stronger guarantees.

foreachBatch error handling:
    Exceptions are NOT swallowed. If the DB write fails the exception propagates
    back to Spark, which will retry the batch according to the streaming retry policy.
"""

import os
import sys
import logging
from datetime import timezone

# Configure HADOOP_HOME for Windows winutils
STREAMING_DIR = os.path.dirname(os.path.abspath(__file__))
HADOOP_DIR = os.path.join(STREAMING_DIR, "hadoop")
if os.path.exists(os.path.join(HADOOP_DIR, "bin", "winutils.exe")):
    os.environ.setdefault("HADOOP_HOME", HADOOP_DIR)
    os.environ.setdefault("hadoop.home.dir", HADOOP_DIR)
    bin_path = os.path.join(HADOOP_DIR, "bin")
    if bin_path not in os.environ.get("PATH", ""):
        os.environ["PATH"] = bin_path + os.pathsep + os.environ.get("PATH", "")

# Ensure PySpark workers on Windows use the current Python interpreter
os.environ.setdefault("PYSPARK_PYTHON", sys.executable)
os.environ.setdefault("PYSPARK_DRIVER_PYTHON", sys.executable)

import psycopg2
from psycopg2.extras import execute_values

from pyspark.sql import SparkSession
from pyspark.sql.functions import (
    col,
    from_json,
    to_timestamp,
    window,
    count,
    approx_count_distinct,
)
from pyspark.sql.types import (
    StructType,
    StructField,
    StringType,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("SparkStreamingAnalytics")

# -----------------------------------------------------------------------------
# Configuration
# -----------------------------------------------------------------------------
KAFKA_BOOTSTRAP_SERVERS = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")
KAFKA_CHAT_TOPIC = os.getenv("KAFKA_CHAT_TOPIC", "chat-events")
KAFKA_STARTING_OFFSETS = os.getenv("KAFKA_STARTING_OFFSETS", "earliest")

PG_HOST = os.getenv("POSTGRES_HOST", "localhost")
PG_PORT = int(os.getenv("POSTGRES_PORT", "5433"))
PG_DB = os.getenv("POSTGRES_DB", "chatapp")
PG_USER = os.getenv("POSTGRES_USER", "chatapp")
PG_PASSWORD = os.getenv("POSTGRES_PASSWORD", "chatapp")

CHECKPOINT_BASE = os.getenv("CHECKPOINT_BASE", "./checkpoints")


# -----------------------------------------------------------------------------
# Timezone helper
# -----------------------------------------------------------------------------
def _to_utc(naive_dt):
    """Convert a naive datetime (local machine tz) to UTC-aware datetime.

    PySpark's collect() returns datetime objects without tzinfo, interpreted
    as local time. PostgreSQL TIMESTAMP WITH TIME ZONE expects UTC-aware values,
    otherwise psycopg2 sends the local wall-clock number and Postgres stores it
    as-is — which is wrong when local ≠ UTC (e.g. UTC+7 → 7-hour offset in DB).
    """
    if naive_dt is None:
        return None
    # Treat the naive dt as local time, then convert to UTC
    return naive_dt.astimezone(timezone.utc)


# -----------------------------------------------------------------------------
# Database Write Helpers (Idempotent UPSERT via psycopg2)
# Errors propagate up so Spark can retry the batch — do NOT swallow them.
# -----------------------------------------------------------------------------
def get_db_connection():
    return psycopg2.connect(
        host=PG_HOST,
        port=PG_PORT,
        dbname=PG_DB,
        user=PG_USER,
        password=PG_PASSWORD,
    )


def write_messages_per_minute(batch_df, batch_id):
    """Write messages_per_minute batch into PostgreSQL with ON CONFLICT DO UPDATE.

    Raises on DB error so Spark retries the batch (no silent data loss).
    """
    records = batch_df.collect()
    if not records:
        return

    # Convert local naive datetimes → UTC-aware before handing to psycopg2
    data = [
        (_to_utc(r.window_start), _to_utc(r.window_end), r.message_count)
        for r in records
    ]
    query = """
        INSERT INTO stream_messages_per_minute (window_start, window_end, message_count)
        VALUES %s
        ON CONFLICT (window_start, window_end)
        DO UPDATE SET message_count = EXCLUDED.message_count;
    """
    conn = get_db_connection()
    try:
        cur = conn.cursor()
        execute_values(cur, query, data)
        conn.commit()
        cur.close()
        logger.info(
            "[Batch %s] Upserted %d rows → stream_messages_per_minute", batch_id, len(data)
        )
    except Exception:
        conn.rollback()
        raise  # let Spark retry the batch
    finally:
        conn.close()


def write_active_users_per_minute(batch_df, batch_id):
    """Write active_users_per_minute batch into PostgreSQL with ON CONFLICT DO UPDATE.

    active_users is computed by approx_count_distinct (HyperLogLog) — exact
    count distinct is not supported in streaming aggregations.
    Raises on DB error so Spark retries the batch.
    """
    records = batch_df.collect()
    if not records:
        return

    data = [
        (_to_utc(r.window_start), _to_utc(r.window_end), r.active_users)
        for r in records
    ]
    query = """
        INSERT INTO stream_active_users_per_minute (window_start, window_end, active_users)
        VALUES %s
        ON CONFLICT (window_start, window_end)
        DO UPDATE SET active_users = EXCLUDED.active_users;
    """
    conn = get_db_connection()
    try:
        cur = conn.cursor()
        execute_values(cur, query, data)
        conn.commit()
        cur.close()
        logger.info(
            "[Batch %s] Upserted %d rows → stream_active_users_per_minute", batch_id, len(data)
        )
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def write_messages_per_conversation(batch_df, batch_id):
    """Write messages_per_conversation batch into PostgreSQL with ON CONFLICT DO UPDATE.

    Raises on DB error so Spark retries the batch.
    """
    records = batch_df.collect()
    if not records:
        return

    data = [
        (_to_utc(r.window_start), _to_utc(r.window_end), str(r.conversation_id), r.message_count)
        for r in records
    ]
    query = """
        INSERT INTO stream_messages_per_conversation (window_start, window_end, conversation_id, message_count)
        VALUES %s
        ON CONFLICT (window_start, window_end, conversation_id)
        DO UPDATE SET message_count = EXCLUDED.message_count;
    """
    conn = get_db_connection()
    try:
        cur = conn.cursor()
        execute_values(cur, query, data)
        conn.commit()
        cur.close()
        logger.info(
            "[Batch %s] Upserted %d rows → stream_messages_per_conversation", batch_id, len(data)
        )
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


# -----------------------------------------------------------------------------
# Main Streaming Job
# -----------------------------------------------------------------------------
def run_pipeline():
    logger.info("Starting Spark Streaming Pipeline...")
    logger.info("Kafka Servers: %s | Topic: %s", KAFKA_BOOTSTRAP_SERVERS, KAFKA_CHAT_TOPIC)
    logger.info("PostgreSQL Target: %s:%s/%s", PG_HOST, PG_PORT, PG_DB)

    # Build SparkSession with Kafka SQL package
    spark = (
        SparkSession.builder
        .appName("ChatStreamingAnalytics")
        .master("local[2]")
        .config("spark.sql.streaming.forceDeleteTempCheckpointLocation", "true")
        .config("spark.sql.shuffle.partitions", "2")
        .config("spark.jars.packages", "org.apache.spark:spark-sql-kafka-0-10_2.12:3.5.5")
        .getOrCreate()
    )

    spark.sparkContext.setLogLevel("WARN")

    # Define Event Schema
    event_schema = StructType([
        StructField("event_type", StringType(), True),
        StructField("message_id", StringType(), True),
        StructField("user_id", StringType(), True),
        StructField("conversation_id", StringType(), True),
        StructField("message_type", StringType(), True),
        StructField("timestamp", StringType(), True),
    ])

    # 1. Read Stream from Kafka
    raw_stream = (
        spark.readStream
        .format("kafka")
        .option("kafka.bootstrap.servers", KAFKA_BOOTSTRAP_SERVERS)
        .option("subscribe", KAFKA_CHAT_TOPIC)
        .option("startingOffsets", KAFKA_STARTING_OFFSETS)
        .option("failOnDataLoss", "false")
        .load()
    )

    # 2. Parse JSON & Filter
    parsed_stream = (
        raw_stream
        .select(from_json(col("value").cast("string"), event_schema).alias("data"))
        .select("data.*")
        .filter(col("event_type") == "message_sent")
        .withColumn("event_time", to_timestamp(col("timestamp")))
        .filter(col("event_time").isNotNull())
    )

    # 3. Deduplicate within each micro-batch using message_id
    #    Protects against at-least-once Kafka delivery producing duplicates.
    #    We deduplicate BEFORE aggregation so counts remain accurate.
    deduped_stream = parsed_stream.dropDuplicates(["message_id"])

    # 4. Apply Watermark for late data handling (30 s)
    watermarked_stream = deduped_stream.withWatermark("event_time", "30 seconds")

    # Metric 1: Messages per minute (exact count)
    msg_per_min_df = (
        watermarked_stream
        .groupBy(window(col("event_time"), "1 minute"))
        .agg(count("*").alias("message_count"))
        .select(
            col("window.start").alias("window_start"),
            col("window.end").alias("window_end"),
            col("message_count"),
        )
    )

    # Metric 2: Active users per minute
    # Note: Spark Structured Streaming does not support exact count_distinct on
    # streaming aggregations — approx_count_distinct (HyperLogLog, ~2% error)
    # is the correct and only available approximation here.
    active_users_df = (
        watermarked_stream
        .groupBy(window(col("event_time"), "1 minute"))
        .agg(approx_count_distinct("user_id").alias("active_users"))
        .select(
            col("window.start").alias("window_start"),
            col("window.end").alias("window_end"),
            col("active_users"),
        )
    )

    # Metric 3: Messages per conversation per minute
    msg_per_conv_df = (
        watermarked_stream
        .groupBy(window(col("event_time"), "1 minute"), col("conversation_id"))
        .agg(count("*").alias("message_count"))
        .select(
            col("window.start").alias("window_start"),
            col("window.end").alias("window_end"),
            col("conversation_id"),
            col("message_count"),
        )
    )

    # 5. Sinks via foreachBatch
    query1 = (
        msg_per_min_df.writeStream
        .trigger(processingTime="5 seconds")
        .outputMode("update")
        .foreachBatch(write_messages_per_minute)
        .option("checkpointLocation", os.path.join(CHECKPOINT_BASE, "msg_per_min"))
        .start()
    )

    query2 = (
        active_users_df.writeStream
        .trigger(processingTime="5 seconds")
        .outputMode("update")
        .foreachBatch(write_active_users_per_minute)
        .option("checkpointLocation", os.path.join(CHECKPOINT_BASE, "active_users"))
        .start()
    )

    query3 = (
        msg_per_conv_df.writeStream
        .trigger(processingTime="5 seconds")
        .outputMode("update")
        .foreachBatch(write_messages_per_conversation)
        .option("checkpointLocation", os.path.join(CHECKPOINT_BASE, "msg_per_conv"))
        .start()
    )

    logger.info("All 3 streaming queries started. Awaiting termination...")
    spark.streams.awaitAnyTermination()


if __name__ == "__main__":
    run_pipeline()
