# 🏗️ NEXORA: System Architecture

NEXORA is built on a decoupled, event-driven, high-performance architecture. It separates fast in-memory operational state (Redis) from durable data persistence (MongoDB), utilizing ultra-low latency LLM inference (Groq) for conversational intelligence.

## 🗺️ High-Level System Architecture

```mermaid
graph TD
    subgraph Client Layer
        Harness["Grading Judge Harness (HTTP Client)"]
        Dashboard["Next.js Ops Dashboard (React UI)"]
    end

    subgraph API Gateway & Guard Layers
        Router["FastAPI Router Orchestrator"]
        RateLimit["RateLimitMiddleware (IP Sliding Window)"]
        PayloadSize["PayloadSizeMiddleware (2MB Cap)"]
        Logger["RequestLoggingMiddleware (JSON logging)"]
    end

    subgraph Endpoint Services
        ContextAPI["/v1/context (Context Ingestion)"]
        TickAPI["/v1/tick (Trigger Periodic Evaluation)"]
        ReplyAPI["/v1/reply (Conversational Turn Handler)"]
        DashboardAPI["/v1/dashboard/* (Metrics API)"]
    end

    subgraph Core Processing Engines
        PriorityEngine["Trigger Priority Engine (0-100 Scoring)"]
        ContextAssembler["Context Assembler (Category + Merchant + Customer)"]
        PromptBuilder["Prompt Builder (Strategy Prompt Construction)"]
        OutputValidator["Output Validator (Sanitization & Lever Compliance)"]
        StateHandler["Reply Turn State Machine (Auto-reply & intent mapping)"]
    end

    subgraph Data & Storage Layer
        Redis[("Redis Memory Store (hot cache, wait states, rate limits)")]
        Mongo[("MongoDB Database (system of record, logs, contexts)")]
    end

    subgraph AI Inference Layer
        GroqCloud["Groq Cloud LPU inference"]
        PrimaryModel["Llama-3.3-70b-versatile (deterministic, T=0)"]
        FallbackModel["Llama-3.1-8b-instant (automatic failover)"]
    end

    %% Network flow
    Harness -->|HTTP REST| Router
    Dashboard -->|HTTP REST| Router
    
    Router --> RateLimit
    RateLimit --> PayloadSize
    PayloadSize --> Logger
    
    Logger --> ContextAPI
    Logger --> TickAPI
    Logger --> ReplyAPI
    Logger --> DashboardAPI

    %% Context Ingestion Flow
    ContextAPI -->|Idempotency Version Check| Redis
    ContextAPI -->|Durable Context Upsert| Mongo

    %% Tick Flow
    TickAPI -->|Resolve & Rank Triggers| PriorityEngine
    PriorityEngine -->|Check Suppression TTL| Redis
    PriorityEngine -->|Assemble Active Contexts| ContextAssembler
    ContextAssembler -->|Fetch Documents| Mongo
    ContextAssembler --> PromptBuilder
    PromptBuilder -->|Complete Prompt Strategy| GroqCloud
    GroqCloud -->|Stripped JSON Completion| OutputValidator
    OutputValidator -->|Log Audit Action| Mongo
    OutputValidator -->|Set Suppression TTL| Redis
    
    %% Reply Flow
    ReplyAPI -->|Load Conversation Turns| Redis
    ReplyAPI -->|Auto-Reply & Intent Check| StateHandler
    StateHandler --> PromptBuilder
    
    %% Dashboard Flow
    DashboardAPI -->|Read Actions / Ticks Log| Mongo
    DashboardAPI -->|Read Active Version Keys| Redis

    %% LLM details
    GroqCloud --- PrimaryModel
    GroqCloud --- FallbackModel
```

## ⏱️ Request Lifecycle: `POST /v1/tick`

The following sequence diagram outlines the end-to-end flow of evaluating triggers and generating engagement actions:

```mermaid
sequenceDiagram
    autonumber
    actor Judge as Client / Judge
    participant API as FastAPI Router
    participant DB as MongoDB Store
    participant Redis as Redis Cache
    participant Engine as Trigger Priority Engine
    participant Composer as Engagement Composer
    participant Groq as Groq LLM API
    participant Validator as Output Validator

    Judge->>API: POST /v1/tick {now, available_triggers}
    API->>DB: Fetch trigger contexts concurrently
    DB-->>API: Return trigger documents
    API->>Engine: rank_triggers(triggers, now)
    Note over Engine: Calculates 0-100 score based<br/>on 6 parameters (urgency, expiry, etc.)
    Engine-->>API: Ranked list of trigger IDs
    
    loop For each ranked trigger
        API->>Redis: Check if suppressed (suppression_key)
        Redis-->>API: returns is_suppressed
        alt is_suppressed = False
            API->>Composer: compose_for_trigger(trigger_id)
            Composer->>DB: Load Category, Merchant, Customer contexts
            DB-->>Composer: return contexts
            Composer->>Groq: Generate WhatsApp Message (System + User Prompts)
            Groq-->>Composer: Raw JSON output
            Composer->>Validator: validate(output, contexts)
            Note over Validator: Strips URLs, checks levers,<br/>validates CTA and send_as
            Validator-->>Composer: Validated Action Action
            Composer->>DB: Log Action Audit Trail
            Composer->>Redis: Set Suppression Key (7-day TTL)
            Composer-->>API: Action object
        else is_suppressed = True
            Note over API: Skip trigger composition
        end
    end
    API-->>Judge: Response {actions, processing_ms}
```

## 🧩 Component Responsibilities

| Component | Responsibility | Interfaces / Technologies |
| :--- | :--- | :--- |
| **`main.py`** | FastAPI App initialization, lifespan management, global exception handling mapping. | FastAPI, Lifespan |
| **`middleware.py`** | Global rate limiting (Redis fixed-window), payload size capping (2MB), request tracing/latency logging. | Starlette Middleware, Redis |
| **`composer/engine.py`** | Coordinates context loading, trigger execution, validation, and action assembly. | EngagementComposer |
| **`composer/trigger_priority_engine.py`** | Deterministically scores and ranks trigger items before sending them to the LLM. | rank_triggers |
| **`composer/prompt_builder.py`** | Tailors LLM system prompts and user payloads for all 27 trigger kinds. | PromptBuilder |
| **`composer/output_validator.py`** | Inspects, auto-corrects, and validates LLM generation schemas and business constraints. | OutputValidator |
| **`reply/handler.py`** | Manages multi-turn conversation replies, auto-replies, and language shifts. | ReplyHandler |
| **`storage/redis_store.py`** | Fast transactional operations (MULTI/EXEC), TTL rate limiting, suppression checks. | Redis (aioredis) |
| **`storage/mongo_store.py`** | Persistent queries, indexing, bulk inserts, historic context logging. | MongoDB (motor) |

## 🛡️ Model Failover & Resiliency Strategy

To satisfy magicpin's strict 30-second budget, NEXORA handles primary model timeouts and rate limits (HTTP 429) using an automated model failover pipeline:

```mermaid
graph TD
    Start[Inbound Message Composition] --> CallPrimary[Call Llama-3.3-70b-versatile via Groq]
    CallPrimary -->|Success| Validate[Run Output Validator]
    CallPrimary -->|Timeout / 429 Rate Limit / 5xx| RetryPrimary[Retry Primary Model with Backoff]
    RetryPrimary -->|Success| Validate
    RetryPrimary -->|All Retries Fail| Fallback[Call Fallback Llama-3.1-8b-instant]
    Fallback -->|Success| Validate
    Fallback -->|Fail| Degrade[Return degraded action: wait fallbacks]
    Validate -->|Success| Return[Return Validated Action]
    Validate -->|Validation Failure / Repetition| Retry[Retry composition once]
```

### Async Task Lifecycle & Timeout Boundaries
*   **Total API Timeout (`REPLY_TIMEOUT_SECONDS=28`):** The FastAPI request handler caps the entire lifetime of a `/v1/reply` or `/v1/tick` invocation to prevent gateway timeout errors.
*   **Groq API Timeout (`LLM_TIMEOUT_SECONDS=22`):** Calls to the Groq completion endpoint are constrained to 22 seconds, leaving a 6-second window for failovers and database logging.
*   **Trigger Task Timeout (`TICK_TIMEOUT_SECONDS - 2.0`):** Concurrently executed trigger compositions inside `/v1/tick` are wrapped in individual `asyncio.wait_for` tasks, preventing a single hanging LLM call from aborting other successful generations.

## 🔒 Middleware Stack & Security

1.  **`RateLimitMiddleware`**: Keys client requests by IP + Path using Redis. Enforces a maximum of `1200` global requests per minute. Exempts `/v1/healthz` to prevent liveness check failures.
2.  **`PayloadSizeMiddleware`**: Inspects `Content-Length` headers and rejects payloads exceeding `2MB` with an `HTTP 413 Payload Too Large` JSON payload.
3.  **`RequestLoggingMiddleware`**: Records HTTP method, path, response status, and backend latency (`duration_ms`) in structured format.

## 🛠️ Exception Handler Chain

Global exception mapping guarantees that client errors never expose internal stack traces or raw exceptions, returning structured JSON errors instead:

*   **`RequestValidationError`**: Intercepts Pydantic model validation errors. Special handling for malformed JSON returns an `INVALID_JSON` (HTTP 400) code, while semantic errors return a `VALIDATION_ERROR` (HTTP 422) code.
*   **`StarletteHTTPException`**: Catches common HTTP exceptions (e.g. 404, 405) and wraps them into standard JSON envelopes with descriptive error codes.
*   **`Exception` (Fallback)**: Catches unhandled code crashes, logs the traceback internally, and returns `INTERNAL_ERROR` (HTTP 500) to the client without leaking database names or source codes.

## 💾 Storage Layer Architecture

### Redis Key Spaces

| Key Pattern | Data Type | TTL | Purpose |
| :--- | :--- | :--- | :--- |
| `nexora:ctx_version:{scope}:{context_id}` | `String` | Infinite | Tracks the current active version of a context document. |
| `nexora:ctx_count:{scope}` | `String` | Infinite | Cache count of unique contexts loaded (for `/v1/healthz`). |
| `nexora:suppress:{suppression_key}` | `String` | 7 Days | Deduplicates outgoing messages, preventing fatigue. |
| `nexora:conv:{conversation_id}` | `String` | 30 Days | Stores JSON list of conversation turn history. |
| `nexora:conv_sent:{conversation_id}` | `String` | 30 Days | Stores outgoing messages to check for repetition. |
| `nexora:conv_ended:{conversation_id}` | `String` | 30 Days | Flag indicating a finalized, ended conversation. |
| `nexora:conv_wait_until:{conversation_id}`| `String` | 30 Days | ISO timestamp blocking outreach until the specified date. |
| `nexora:auto_reply_count:{conversation_id}`| `String` | 24 Hours | Integer counting consecutive canned replies. |
| `nexora:ratelimit:{key}:{window}` | `String` | 60 Sec | Sliding window counter for rate limiters. |

### MongoDB Collections

*   **`contexts`**: Active versioned payloads. Has a unique index on `(scope, context_id)`.
*   **`contexts_history`**: Historic versions of context pushes for auditability. Indexed on `(scope, context_id, version)`.
*   **`actions_log`**: Log of all actions generated during `/v1/tick`. Indexed on `logged_at` and `merchant_id`.
*   **`replies_log`**: Log of all reply states and LLM usage statistics. Indexed on `logged_at` and `conversation_id`.
*   **`ticks_log`**: Historical trace of tick payloads and execution order. Indexed on `created_at`.
*   **`suppressions_log`**: Durable record of active suppression keys. Unique index on `suppression_key`.

👉 **Next Steps:** Proceed to the [System Design](/docs/03-system-design.md) manual to review modular breakdowns.
