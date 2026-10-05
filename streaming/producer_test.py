"""
Traffic Generator / Stress Test Script for Chat Streaming Analytics.

Simulates chat activity by producing JSON events directly to the Kafka
'chat-events' topic with realistic timestamps, multiple users, and conversations.

Usage:
    python producer_test.py --rate 10 --duration 60
    python producer_test.py --messages 500 --rate 25
"""

import argparse
import json
import logging
import os
import random
import time
import uuid
from datetime import datetime, timezone
from kafka import KafkaProducer

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("TrafficGenerator")

KAFKA_BOOTSTRAP_SERVERS = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")
KAFKA_CHAT_TOPIC = os.getenv("KAFKA_CHAT_TOPIC", "chat-events")

SAMPLE_MESSAGES = [
    "Hello everyone!",
    "How is the streaming analytics performance?",
    "Kafka KRaft is really fast.",
    "Spark Structured Streaming aggregates in 1-minute windows.",
    "Did you see the new metrics in the dashboard?",
    "Testing high-throughput streaming pipeline.",
    "Awesome pair programming!",
    "Great work on the Big Data architecture.",
    "Checking message delivery latency.",
    "All systems operational."
]

def generate_users_and_conversations(num_users=10, num_conversations=4):
    users = [str(uuid.uuid4()) for _ in range(num_users)]
    conversations = [str(uuid.uuid4()) for _ in range(num_conversations)]
    return users, conversations

def run_generator(rate: float, duration: int, total_messages: int | None):
    logger.info(f"Connecting to Kafka at {KAFKA_BOOTSTRAP_SERVERS}...")
    producer = KafkaProducer(
        bootstrap_servers=KAFKA_BOOTSTRAP_SERVERS,
        value_serializer=lambda v: json.dumps(v).encode("utf-8"),
        key_serializer=lambda k: k.encode("utf-8") if k else None,
        # enable.idempotence ensures exactly-once delivery per producer session
        # (requires acks="all" and retries > 0, both set automatically)
        acks="all",
        enable_idempotence=True,
    )

    users, conversations = generate_users_and_conversations()
    logger.info(f"Generated {len(users)} mock users and {len(conversations)} mock conversations.")
    logger.info(f"Target rate: {rate} msgs/sec. Topic: {KAFKA_CHAT_TOPIC}")

    interval = 1.0 / rate if rate > 0 else 0.05
    start_time = time.time()
    sent_count = 0

    try:
        while True:
            now = time.time()
            if duration and (now - start_time) >= duration:
                break
            if total_messages and sent_count >= total_messages:
                break

            user_id = random.choice(users)
            conv_id = random.choice(conversations)
            msg_text = random.choice(SAMPLE_MESSAGES)
            msg_id = str(uuid.uuid4())
            ts = datetime.now(timezone.utc).isoformat()

            event = {
                "event_type": "message_sent",
                "message_id": msg_id,
                "user_id": user_id,
                "conversation_id": conv_id,
                "message_type": "text",
                "timestamp": ts
            }

            producer.send(
                KAFKA_CHAT_TOPIC,
                key=conv_id,
                value=event
            )
            sent_count += 1

            if sent_count % 50 == 0:
                logger.info(f"Sent {sent_count} events (elapsed: {now - start_time:.1f}s)")

            time.sleep(interval)

    except KeyboardInterrupt:
        logger.info("Traffic generator stopped by user.")
    finally:
        producer.flush()
        producer.close()
        elapsed = time.time() - start_time
        logger.info(f"Completed! Total sent: {sent_count} events in {elapsed:.2f}s ({sent_count/elapsed:.1f} msgs/sec).")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Kafka Chat Traffic Simulator")
    parser.add_argument("--rate", type=float, default=5.0, help="Messages per second (default: 5)")
    parser.add_argument("--duration", type=int, default=60, help="Duration in seconds (default: 60)")
    parser.add_argument("--messages", type=int, default=None, help="Total messages to send (optional)")
    args = parser.parse_args()

    run_generator(rate=args.rate, duration=args.duration, total_messages=args.messages)
