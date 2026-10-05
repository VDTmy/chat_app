# REAL-TIME CHAT & STREAMING ANALYTICS PLATFORM

An enterprise-grade Big Data platform combining real-time messaging with a high-throughput streaming analytics pipeline using **FastAPI**, **React**, **Apache Kafka (KRaft mode)**, and **Apache Spark Structured Streaming**.

---

## 1. Architecture Overview

```
                      React + TypeScript (Vite)
                      │                     │
       WebSocket /ws  │                     │ HTTP GET /analytics/*
                      ▼                     ▼
               FastAPI Backend ──────► Analytics Router
                      │                     ▲
         DB Commit    │                     │ SELECT
        ┌─────────────┴─────────────┐       │
        ▼                           ▼       │
PostgreSQL (OLTP)              Kafka Broker │
(users, messages,             (KRaft mode,  │
 conversations)              3 partitions)  │
                                    │       │
                                    ▼       │
                       Spark Structured Streaming
                       ├─ Watermark: 30s    │
                       ├─ Tumbling Window: 1m
                       └─ foreachBatch UPSERT
                                    │
                                    ▼
                       PostgreSQL (Analytics)
                       (stream_messages_per_minute,
                        stream_active_users_per_minute,
                        stream_messages_per_conversation)
```

### Component Responsibilities

| Component | Technology | Sole Responsibility |
|---|---|---|
| **Frontend** | React 19 + TypeScript + Vite + Recharts | Responsive chat interface & real-time analytics dashboard |
| **Backend API** | FastAPI + SQLAlchemy (Async) | REST API, WebSocket server, Kafka producer (fire-and-forget) |
| **Message Broker** | Apache Kafka 3.7 (KRaft mode) | Ingestion buffer for chat events (`chat-events` topic) |
| **Stream Engine** | Apache Spark 3.5 (Structured Streaming) | Event-time windowing, watermarking, aggregations |
| **OLTP Database** | PostgreSQL 16 (Port 5433) | Transactional data storage for chat messages & users |
| **Analytics Storage**| PostgreSQL 16 (`stream_*` tables) | Pre-aggregated metrics storage (idempotent UPSERT) |
| **Cache & Real-time**| Redis 7 | Presence, typing indicators, token blacklist, WS pub/sub |
| **Object Storage** | MinIO | Attachments and file uploads |

---

## 2. Project Directory Structure

```
chat-app/
├── backend/
│   ├── app/
│   │   ├── api/v1/          # REST & WebSocket routes (incl. /analytics)
│   │   ├── core/            # Config, security, dependencies
│   │   ├── db/              # SQLAlchemy session & base
│   │   ├── kafka/           # Kafka producer module (start/stop/publish)
│   │   ├── models/          # OLTP models (User, Message, Conversation)
│   │   ├── redis/           # Cache, pubsub, presence, typing
│   │   ├── services/        # Business logic services
│   │   └── websocket/       # WebSocket manager & event handlers
│   └── main.py              # Application entrypoint & lifespan
├── frontend/
│   ├── src/
│   │   ├── api/             # Axios clients (auth, chat, analytics)
│   │   ├── components/      # Chat UI components (Sidebar, ChatWindow)
│   │   ├── pages/           # ChatPage, LoginPage, AnalyticsPage
│   │   └── store/           # Zustand stores (auth, chat)
│   └── package.json
├── streaming/
│   ├── spark_streaming.py   # Spark Structured Streaming job
│   ├── producer_test.py     # High-throughput traffic generator
│   ├── requirements.txt     # PySpark, psycopg2 dependencies
│   └── README.md
├── sql/
│   └── analytics_schema.sql # DDL for PostgreSQL analytics tables
├── report/
│   └── report.tex           # Academic & technical evaluation report
├── docker-compose.yml       # PostgreSQL, Redis, MinIO, Kafka KRaft
└── README.md
```

---

## 3. Quick Start & Execution Guide

### Step 1: Start Infrastructure Containers

Run Docker Compose to start PostgreSQL, Redis, MinIO, and Kafka (with automatic topic initialization):

```bash
docker compose up -d
```

Verify that all services are healthy:
- PostgreSQL: `localhost:5433`
- Redis: `localhost:6379`
- MinIO: `localhost:9000` (Console: `localhost:9001`)
- Kafka KRaft: `localhost:9092`

### Step 2: Initialize Database Schemas

1. **OLTP Schema (Migrations via Alembic):**
   ```bash
   cd backend
   alembic upgrade head
   ```

2. **Analytics Tables Schema:**
   ```bash
   # From root directory:
   docker exec -i chatapp_postgres psql -U chatapp -d chatapp < sql/analytics_schema.sql
   ```

### Step 3: Run the Backend (FastAPI)

```bash
cd backend
pip install -r requirements.txt
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```
- API Documentation: `http://localhost:8000/docs`
- Analytics Endpoints: `http://localhost:8000/api/v1/analytics/*`

### Step 4: Run the Frontend (React + Vite)

```bash
cd frontend
npm install
npm run dev
```
- Chat Interface: `http://localhost:5173/chat`
- Streaming Analytics Dashboard: `http://localhost:5173/analytics` (or click the Analytics chart icon in the chat header)

---

## 4. Running the Big Data Streaming Pipeline

### Step 5: Start Apache Spark Structured Streaming

Ensure Python dependencies are installed in your virtual environment:

```bash
cd streaming
pip install -r requirements.txt
```

Launch the streaming job:
```bash
python spark_streaming.py
```
*Note: Spark will consume from Kafka `chat-events`, aggregate in 1-minute tumbling windows with a 30s watermark, and write to PostgreSQL analytics tables via idempotent UPSERT (`foreachBatch`).*

### Step 6: Simulate Traffic / Stress Testing

To simulate realistic high-volume chat traffic and watch the live charts in the dashboard:

```bash
cd streaming

# Send 10 messages/second for 60 seconds across multiple mock users:
python producer_test.py --rate 10 --duration 60

# Or benchmark with 500 messages at 25 msgs/sec:
python producer_test.py --rate 25 --messages 500
```

---

## 5. Streaming Semantics & Guarantees

1. **Fire-and-Forget Ingestion**: Chat messages are committed to the operational database (PostgreSQL) *first*. Publishing to Kafka occurs immediately after. If Kafka is unavailable, errors are logged without interrupting or crashing the user's chat experience.
2. **Conversation Ordering Guarantee**: Messages use `conversation_id` as the Kafka partition key, guaranteeing that all messages from the same conversation arrive on the same partition in sequential order.
3. **Event-Time Watermark (30s)**: Handles late-arriving events due to network delays while bounding the memory state maintained by Spark.
4. **Idempotent Micro-Batch Sinks**: Spark's `foreachBatch` writes using SQL `ON CONFLICT (...) DO UPDATE` (UPSERT), ensuring consistency across re-executions or restarts without duplicate primary key errors.

---

## 6. Academic Technical Report

The formal technical paper detailing the system architecture, benchmarks, and performance analysis is available in the `report/` folder:
- Source LaTeX: [`report/report.tex`](file:///d:/Đại%20học/Dự%20án/chat-app/report/report.tex)
