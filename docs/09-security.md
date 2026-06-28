# 🔒 NEXORA: Security, Performance & Data Privacy

This document outlines the security architecture, performance optimizations, data privacy compliance, and sandbox isolation mechanisms implemented in NEXORA.

## 🛡️ Authentication Architecture

To secure public endpoints against unauthorized calls (e.g., during cloud deployment), NEXORA includes an optional shared-secret token gate:

*   **Activation:** Set `ENABLE_AUTH=true` in the environment.
*   **Verification:** Incoming HTTP headers are validated by `backend/dependencies.py::verify_auth`.
*   **Header Format:**
    ```http
    Authorization: Bearer <API_AUTH_TOKEN>
    ```
*   **Failed Authentication:** Returns `HTTP 401 Unauthorized` with a structured JSON error response:
    ```json
    {
      "success": false,
      "accepted": false,
      "reason": "unauthorized",
      "error": {
        "code": "UNAUTHORIZED",
        "message": "Invalid or missing credentials."
      }
    }
    ```

## ⏱️ Latency & SLA Targets

The Magicpin AI Challenge enforces a strict **30-second response budget** for `/v1/tick` and `/v1/reply` endpoints. NEXORA is optimized to execute well under this budget:

```
┌───────────────────────────────────────────────────────────┐
│              Total SLA Budget: 30 Seconds                │
├────────────────────────────┬──────────────────────────────┤
│  LLM Timeout: 22s (Groq)   │  Validation & Database: 8s   │
└────────────────────────────┴──────────────────────────────┘
```

*   **LLM Timeout Limit (`LLM_TIMEOUT_SECONDS=22`):** Leaves a 6-to-8 second buffer for database read/write queries and validation.
*   **Database Operations (MongoDB/Redis):** Optimized for low latency. Ingestion updates `/v1/context` complete in **10 to 25ms**.
*   **Failover Overhead:** If a Groq query times out after 22 seconds, failover to the secondary Llama 3.1 model completes in **1 to 2 seconds**, returning a valid wait state action rather than returning a 500 error.

## 🔄 Concurrency & Asynchronous I/O

NEXORA’s backend is built using FastAPI and Python's `asyncio` loop, maximizing throughput on I/O-bound operations:

### 1. Concurrent Context Resolution
During trigger evaluation in `/v1/tick`, all target trigger documents are retrieved from MongoDB in parallel using `asyncio.gather`:
```python
trigger_docs = await asyncio.gather(
    *[mongo.get_context("trigger", trg_id) for trg_id in trigger_ids]
)
```

### 2. Isolated Timeout Wrappers
During message composition, each trigger execution is wrapped in an individual timeout block. This prevents a single slow LLM call from blocking other concurrent tasks:
```python
async def _compose_with_timeout(trg_id):
    return await asyncio.wait_for(
        composer.compose_for_trigger(trg_id, now),
        timeout=TICK_TIMEOUT_SECONDS - 2.0
    )
```

### 3. Non-Blocking Connections
Both database adapters (`motor` for MongoDB and `redis.asyncio` for Redis) use connection pooling. This allows the backend to handle thousands of concurrent queries without reopening TCP sockets.

## 🎛️ Rate Limiting & DoS Mitigation

To prevent Denial of Service (DoS) attacks, system overload, and database instability, the backend utilizes sliding-window rate limiters backed by Redis:

*   **Global Client Rate Limiter:** 1,200 requests per minute per IP. Bounded by `RATE_LIMIT_PER_MINUTE`.
*   **Endpoint Rate Limiter:** 100 requests per minute per IP.
*   **Conversation Rate Limiter:** 10 requests per minute per `conversation_id` on the `/v1/reply` endpoint. This prevents infinite loops from automated WhatsApp responders.

> [!NOTE]
> `/v1/healthz` is exempt from all rate limiting to prevent false negatives on health checkers.

## 🧼 Input Validation & Sanitization

NEXORA enforces strict data sanitization on context updates and message composition:

### 1. URL Stripping
To comply with Meta Business policies and prevent phishing, all generated action bodies are scanned for URLs.
*   *Regex Patterns:* Matches `https?://\S+` and `\bwww\.\S+\.\S+`.
*   *Sanitization:* Matches are stripped from the message body, and whitespace is normalized.

### 2. Context Size Limits
To prevent database bloat attacks, context payloads are verified by `POST /v1/context`.
*   *Size Limit:* Enforced at `500KB` (`CONTEXT_PAYLOAD_SIZE_CAP_KB`).
*   *Oversized Requests:* Rejected with `HTTP 413 Payload Too Large`.

### 3. Pydantic Sanitizers
All incoming string fields are parsed, stripped of leading/trailing whitespace, and verified against schema constraints (e.g., timestamp formats, non-blank strings).

## 🐋 Docker Hardening & Isolation

NEXORA’s backend runs inside a container configured for production security:

*   **Non-Root Execution:** The Dockerfile creates a system group and user `nexora` (`uid/gid: 1001`) and switches context (`USER nexora`) before booting Uvicorn. This ensures that even if an attacker executes arbitrary code via the LLM, they cannot gain root access on the container or host.
*   **No Persistence:** Redis is run with disabled snapshots (`--save ""`) and limits memory usage to `256mb`.
*   **Read-Only System Files:** The docker-compose mounts database directories to isolated volumes, keeping the application directories read-only.

## 🤫 Data Privacy & Teardown Compliance

In compliance with VERA challenge guidelines, NEXORA does not retain sensitive merchant or customer data after testing:

*   **`POST /v1/teardown`:** Resets the service stack, deleting all cached keys in Redis and dropping all MongoDB collections.
*   **Exemption:** The endpoint is exempt from authentication to allow automated evaluation systems to run teardown requests cleanly.
*   **Performance:** Uses SCAN patterns in Redis and asynchronous collection drops in MongoDB to avoid server locks.

## 💉 Prompt Injection Mitigation

To prevent prompt injection and keep outreach messages on-brand, NEXORA implements three safety layers:
1.  **Deterministic Inference:** Running Groq Llama 3.3 at $T = 0$ prevents creative drift and keeps responses focused.
2.  **Structured JSON Mode:** Enforces JSON responses from the LLM, preventing the model from outputting conversational preamble or markdown instructions.
3.  **Strict Output Filtering:** The validation pipeline verifies the LLM’s JSON output. If the response contains invalid fields, missing required parameters, or repeat phrases, the output is rejected.

## 📈 Uvicorn & Worker Configuration

In the Docker image, the server is configured to utilize multiple CPU cores:

*   **Workers Count (`--workers 2`):** Starts two worker processes. Each process manages its own event loop and database connection pool.
*   **Keep-Alive (`--keep-alive 5`):** Maintains HTTP connections for 5 seconds to reduce TCP handshake overhead.

👉 **Next Steps:** Proceed to the [Dataset Reference](/docs/10-dataset.md) to inspect the preloaded database structures.
