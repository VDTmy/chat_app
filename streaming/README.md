# Streaming Analytics Pipeline (Apache Spark Structured Streaming)

This module handles real-time stream processing for the **Real-Time Chat & Streaming Analytics Platform**.

## Architecture

```
FastAPI WebSocket / REST
         │
         ▼
Kafka Topic ("chat-events")
         │
         ▼
Spark Structured Streaming Job (spark_streaming.py)
   ├─ Watermark: 30s
   ├─ Tumbling Window: 1 minute
   ├─ dropDuplicates(["message_id"])  ← guards against at-least-once re-delivery
   │
   ├─ Aggregation 1: Total Messages / Minute  (exact count)
   ├─ Aggregation 2: Active Users / Minute   (approx_count_distinct — HyperLogLog)
   └─ Aggregation 3: Messages / Conversation / Minute
         │
         ▼
PostgreSQL Analytics Tables (UPSERT via foreachBatch)
   ├─ stream_messages_per_minute         (TIMESTAMP WITH TIME ZONE — stored as UTC)
   ├─ stream_active_users_per_minute
   └─ stream_messages_per_conversation
         │
         ▼
FastAPI Analytics Router (/api/v1/analytics/*)
         │
         ▼
React Analytics Dashboard (/analytics)
```

## Prerequisites

1. **Java JDK**: Java 11 or 17 installed and `JAVA_HOME` set.
2. **Python Environment**: Python 3.10+ with packages installed:
   ```bash
   pip install -r requirements.txt
   ```
3. **Database & Kafka**:
   Ensure Docker containers are running:
   ```bash
   docker compose up -d postgres kafka kafka-init redis
   ```
4. **Analytics SQL Schema**:
   Apply the analytics schema if not already initialized:
   ```bash
   # From root project directory
   psql -h localhost -p 5433 -U chatapp -d chatapp -f sql/analytics_schema.sql
   ```

## Running the Spark Structured Streaming Pipeline

### Option 1: Direct Python Execution (recommended for dev)
```bash
python spark_streaming.py
```
PySpark downloads the Kafka connector JAR automatically on first run
(`org.apache.spark:spark-sql-kafka-0-10_2.12:3.5.5`).

### Option 2: Using spark-submit
```bash
spark-submit \
  --master "local[*]" \
  --packages org.apache.spark:spark-sql-kafka-0-10_2.12:3.5.5 \
  spark_streaming.py
```

> **Windows note — `HADOOP_HOME` / `winutils` (Đã được cấu hình tự động)**
>
> Trên Windows, Hadoop yêu cầu `winutils.exe` và `hadoop.dll`. Dự án đã bao gồm sẵn các file này trong `streaming/hadoop/bin/` và `spark_streaming.py` sẽ tự động cấu hình `HADOOP_HOME` cùng `PYSPARK_PYTHON` khi khởi chạy.
> Bạn chỉ cần chạy trực tiếp:
> ```powershell
> python spark_streaming.py
> ```

## Timezone Handling

Spark `collect()` returns `datetime` objects in the **local machine timezone** (naive, no tzinfo).
PostgreSQL columns are `TIMESTAMP WITH TIME ZONE` and expect UTC-aware values.

Without correction, a UTC+7 machine writes wall-clock time as if it were UTC — causing a **7-hour
offset** in the analytics tables (future timestamps on the dashboard).

The fix in `spark_streaming.py`:
```python
from datetime import timezone

def _to_utc(naive_dt):
    return naive_dt.astimezone(timezone.utc)  # local → UTC-aware
```
Applied to every `window_start` / `window_end` before the psycopg2 INSERT.

To verify the fix is working:
```sql
SHOW timezone;                                                      -- should be UTC
SELECT window_start, now() FROM stream_messages_per_minute
ORDER BY 1 DESC LIMIT 3;                                            -- window_start ≤ now()
```

## Active Users Metric: approx_count_distinct

Spark Structured Streaming does **not** support exact `COUNT(DISTINCT …)` in streaming
aggregations. The pipeline uses `approx_count_distinct` (HyperLogLog sketch, ~2% relative error).

The `stream_active_users_per_minute.active_users` column therefore stores approximate values.
The dashboard labels this correctly as `approx_count_distinct`.

## Running the Traffic Generator / Benchmark Test

To simulate chat events and see real-time updates in the dashboard without manual chatting:

```bash
# Send 10 messages per second for 60 seconds:
python producer_test.py --rate 10 --duration 60

# Send 500 messages total at 25 msgs/sec:
python producer_test.py --rate 25 --messages 500
```

The producer uses `enable_idempotence=True` + `acks="all"` to prevent duplicate events on retry.
Spark additionally deduplicates on `message_id` within each micro-batch.
