"""
config.py — Central configuration for IncidentMind.

Loads API keys from .env and exposes all tunable constants so the rest
of the codebase never hard-codes credentials or magic values.
"""

import os
from dotenv import load_dotenv

# Load .env from the project root
load_dotenv()

# ── Hindsight (Vectorize) ──────────────────────────────────────────────────────
HINDSIGHT_API_KEY: str = os.getenv("HINDSIGHT_API_KEY", "")
HINDSIGHT_BASE_URL: str = "https://api.hindsight.vectorize.io"

# Memory bank dedicated to this project (idempotent across restarts)
HINDSIGHT_BANK_ID: str = "incidentmind-v1"

# Number of similar past incidents to recall before calling the LLM
RECALL_TOP_K: int = 5

# ── Groq LLM ──────────────────────────────────────────────────────────────────
GROQ_API_KEY: str = os.getenv("GROQ_API_KEY", "")

# Primary model — try this first
GROQ_PRIMARY_MODEL: str = "openai/gpt-oss-120b"

# Fallback model — used if primary returns an error
GROQ_FALLBACK_MODEL: str = "qwen/qwen3-32b"

# Groq request limits
GROQ_MAX_TOKENS: int = 4096
GROQ_TEMPERATURE: float = 0.2      # Low temperature for deterministic root-cause analysis
GROQ_MAX_RETRIES: int = 3          # Retry attempts before switching to fallback

# ── Demo config ───────────────────────────────────────────────────────────────
# 3 demo incidents that can be pasted in one click during a live demo
DEMO_INCIDENTS = [
    {
        "label": "🔴 payments-api Timeout Storm",
        "text": (
            "ALERT: payments-api P0 — 98% of requests timing out\n"
            "Service: payments-api  Region: us-east-1  Time: 2026-09-28T08:12Z\n\n"
            "Error log:\n"
            "ERROR [payments-api] Connection pool exhausted: max_connections=100\n"
            "ERROR [payments-api] com.zaxxer.hikari.pool.HikariPool: Connection is not "
            "available, request timed out after 30000ms\n"
            "ERROR [payments-api] PSQLException: FATAL: remaining connection slots are "
            "reserved for non-replication superuser connections\n\n"
            "Metrics: latency_p99=28400ms, active_connections=100, queue_depth=847, "
            "CPU=12%, Memory=34%"
        ),
    },
    {
        "label": "🟡 auth-service JWT Failures",
        "text": (
            "ALERT: auth-service — 100% of login attempts returning 401\n"
            "Service: auth-service  Region: us-west-2  Time: 2026-09-28T09:45Z\n\n"
            "Error log:\n"
            "ERROR [auth-service] JWT signature verification failed: "
            "SignatureException: JWT signature does not match locally computed signature\n"
            "ERROR [auth-service] redis.exceptions.ConnectionError: "
            "Error 111 connecting to redis-cache:6379. Connection refused.\n"
            "ERROR [auth-service] Cache miss rate: 100% — falling back to DB\n\n"
            "Metrics: error_rate=100%, latency_p50=4200ms, redis_connected=false, "
            "db_queries/sec=8400 (normal: 200)"
        ),
    },
    {
        "label": "🟠 order-queue Message Backlog",
        "text": (
            "ALERT: order-queue — consumer lag critical, 847k messages unprocessed\n"
            "Service: order-queue  Region: eu-west-1  Time: 2026-09-28T11:22Z\n\n"
            "Error log:\n"
            "ERROR [order-queue] KafkaConsumer: offset commit failed after 3 retries\n"
            "ERROR [order-queue] java.lang.OutOfMemoryError: GC overhead limit exceeded\n"
            "ERROR [order-queue] Consumer group 'order-processor' rebalancing — "
            "max.poll.records=500, processing_time_per_batch=45s (limit: 30s)\n\n"
            "Metrics: consumer_lag=847312, memory_usage=98%, gc_pause_time=8200ms, "
            "throughput=0 msg/s (normal: 12000 msg/s)"
        ),
    },
]
