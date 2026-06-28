# 🏗️ NEXORA: System Design

NEXORA is designed around modular, decoupled components following Domain-Driven Design (DDD) principles. This ensures separation of concerns, testability, and clean maintainability.

## 🧩 Architectural Modular Breakdown

The system is split into distinct layers:

```mermaid
graph TD
    subgraph Client Layer [Client Layer]
        Harness["Grading Judge Harness (HTTP Client)"]
        Dashboard["React Frontend Dashboard (Vite/Next.js)"]
    end

    subgraph API Routing Layer [API Routing Layer]
        Router["FastAPI Gateway Router"]
        Controllers["Endpoint Controllers (/context, /tick, /reply, /teardown)"]
    end

    subgraph Middleware Layer [Middleware & Guard Layer]
        RateLimit["RateLimitMiddleware (IP sliding-window)"]
        PayloadSize["PayloadSizeMiddleware (2MB payload cap)"]
        Logger["RequestLoggingMiddleware (structured JSON logger)"]
    end

    subgraph Core Logic Layer [Core Application Layer]
        subgraph Composition Core
            Composer["EngagementComposer Engine"]
            ContextAssembler["ContextAssembler (Context aggregation)"]
            PromptBuilder["PromptBuilder (Campaign strategies)"]
            OutputValidator["OutputValidator (Lever enforcement)"]
        end

        subgraph Conversation Core
            ReplyHandler["ReplyHandler"]
            IntentRouter["IntentRouter (Commit detection)"]
            AutoReplyDetector["AutoReplyDetector (Bot signatures)"]
            LangDetector["LanguageDetector (Hinglish/Hindi/English)"]
        end
    end

    subgraph Data Access Layer [Data Access Layer]
        RedisStore["RedisStore (Transactional state, TTLs, wait-states)"]
        MongoStore["MongoStore (Durable persistence, history)"]
    end

    %% Routing connections
    Harness & Dashboard --> Router
    Router --> RateLimit --> PayloadSize --> Logger --> Controllers

    %% Logic connections
    Controllers -->|Context Data| DataAccess
    Controllers -->|Trigger Tick| Composition
    Controllers -->|Merchant Reply| Conversation

    subgraph Composition [Composition Pipeline]
        Composer --> ContextAssembler
        ContextAssembler --> PromptBuilder
        PromptBuilder --> OutputValidator
    end

    subgraph Conversation [Conversation State Machine]
        ReplyHandler --> AutoReplyDetector
        AutoReplyDetector --> IntentRouter
        IntentRouter --> LangDetector
    end

    subgraph DataAccess [Data Access Hub]
        RedisStore
        MongoStore
    end

    Composition & Conversation --> DataAccess
```

## ⚙️ Core Subsystem Designs

### 1. Context Assembler
*   **Module:** `backend/composer/context_assembler.py`
*   **Design Pattern:** Facade / Factory
*   **Responsibility:** Given a target `trigger_id` and the current timestamp, it queries MongoDB to retrieve:
    *   The `trigger` context document.
    *   The `merchant` context document referenced by the trigger.
    *   The `category` context document matching the merchant's vertical.
    *   The `customer` context document (only if the trigger has a `customer` scope).
*   **Resilience Logic:** It validates the schema structure. If any critical database context is missing or corrupted, it returns `None` safely instead of raising exceptions, preventing a single corrupted record from halting tick execution.

### 2. Prompt Builder & Dispatcher
*   **Module:** `backend/composer/prompt_builder.py`
*   **Design Pattern:** Strategy Pattern
*   **Responsibility:** Dynamic prompt construction. It injects a global system prompt enforcing general boundaries (no URLs, code-mixing guidance, constraint mapping), and appends trigger-specific system prompts dynamically based on `trigger.kind`.
*   **Prompt Grounding:** Avoids hallucination by structuring raw context data inside markdown blocks (e.g., `## MERCHANT CONTEXT` and `## CUSTOMER CONTEXT`) directly readable by the LLM.

### 3. Output Validation Pipeline
*   **Module:** `backend/composer/output_validator.py`
*   **Design Pattern:** Pipeline / Chain of Responsibility
*   **Responsibility:** Enforces system invariants on raw LLM string completions before delivery.

```mermaid
graph TD
    Raw[Raw LLM Output JSON] --> ValidateDict{Is Dictionary?}
    ValidateDict -->|No| Fail[Reject & Return None]
    ValidateDict -->|Yes| CheckBody{Is Body Empty?}
    
    CheckBody -->|Yes| Fail
    CheckBody -->|No| StripURLs[Strip HTTP/WWW URLs]
    
    StripURLs --> RepetitionCheck{Is Repetitive in Thread?}
    RepetitionCheck -->|Yes| Fail
    RepetitionCheck -->|No| LeverCheck{At Least 1 Compulsion Lever?}
    
    LeverCheck -->|No| Retry[Signal Retry to Composer]
    LeverCheck -->|Yes| CTACheck[Validate & Backfill CTA]
    
    CTACheck --> ScopeCheck[Verify & Auto-correct send_as scope]
    ScopeCheck --> TabooCheck[Scan for Taboo Words]
    TabooCheck --> LogAction[Log Action to MongoDB & Set Redis Suppression]
```

### 4. Multi-Turn Conversation Manager
*   **Module:** `backend/reply/handler.py`
*   **Design Pattern:** State Pattern
*   **Responsibility:** Drives reply decisions (`send` | `wait` | `end`) using in-memory Redis conversation logs.
*   **Core Detectors:**
    *   `AutoReplyDetector`: Checks for automated WhatsApp responder signatures.
    *   `IntentRouter`: Identifies commit indicators (`"yes"`, `"let's go"`) to skip discovery and enter execution mode.
    *   `LanguageDetector`: Analyzes the inbound message language and directs the LLM to mirror it.

| Inbound User Message | State Machine Transition Action | Redis Status Keys Modified |
| :--- | :--- | :--- |
| **Stop / Unsubscribe** | Transition to `Ended`. Block all future outreach actions. | Set `nexora:conv_ended:{conv_id}` to `True` |
| **Yes / Confirm / Book** | Transition to `ActionMode`. Pass instruction overrides to prompter. | Update latest message intent in `nexora:conv:{conv_id}` |
| **Auto-Reply (Strike 1)** | Generate a gentle nudge prompt to encourage actual human input. | Increment `nexora:auto_reply_count:{conv_id}` |
| **Auto-Reply (Strike 2)** | Transition to `WaitState`. Lock thread and block evaluations for 24 hours. | Set `nexora:conv_wait_until:{conv_id}` with 24h TTL |
| **Auto-Reply (Strike 3)** | Transition to `Ended`. Block conversation thread completely. | Set `nexora:conv_ended:{conv_id}` to `True` |

## 🧬 Design Patterns in Action

NEXORA implements established software engineering patterns to handle complex AI workflow logic cleanly:

*   **Singleton Pattern (Database Connections):** `RedisStore` and `MongoStore` instances are initialized once during the FastAPI application lifecycle and shared across all routing endpoints via FastAPI's dependency injection container, preserving connection pooling efficiency.
*   **Strategy Pattern (Prompt Generation):** `PromptBuilder` uses trigger-specific strategy blocks to customize system instructions and data grounding based on the trigger kind (e.g. chronic refill reminders, competitor alerts, seasonal shift prompts).
*   **Chain of Responsibility (Output Validation):** `OutputValidator` evaluates the generated text through a linear validation pipeline. Each block (URL stripping, repetition checks, lever counts, taboo keyword searches) has the opportunity to sanitise, approve, or reject the message.

## 🔀 Idempotent Ingestion & Monotonic Version Checks

The `/v1/context` ingestion pipeline enforces absolute consistency using the following double-check mechanism:

```mermaid
sequenceDiagram
    autonumber
    Client->>FastAPI: POST /v1/context {scope, context_id, version, payload}
    FastAPI->>Redis: GET nexora:ctx_version:{scope}:{context_id}
    alt Cached Version Exists and Version >= Request Version
        Redis-->>FastAPI: Return Cached Version
        FastAPI-->>Client: HTTP 200 {accepted: false, reason: "stale_version"}
    else Version is Monotonically Greater (or New Context)
        Redis-->>FastAPI: Return Null / Older Version
        FastAPI->>Mongo: Bulk Write Context Document & Context History Log
        FastAPI->>Redis: SET nexora:ctx_version:{scope}:{context_id} = Request Version
        FastAPI-->>Client: HTTP 200 {accepted: true, ack_id: "..."}
    end
```

## 📊 Database Engine Strategy

NEXORA splits data persistence across two datastores:

### 1. Redis (Operational Memory)
Redis acts as a high-throughput, low-latency transaction hub. All context versions are registered in Redis using atomic pipelines (`MULTI/EXEC`) to avoid race conditions. Suppressions, rate limits, and conversation wait-states are enforced using Redis TTL keys to guarantee automatic cleanup.

### 2. MongoDB (System of Record)
MongoDB acts as the durable database. Full context documents are stored as flexible documents, accommodating heterogeneous fields. Every outbound action and inbound reply turn is persistently logged in MongoDB to compile comprehensive dashboards and audit logs.

👉 **Next Steps:** Proceed to the [Data Flow Design](/docs/04-data-flow.md) guide to inspect how data passes through these components.
