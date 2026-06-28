# ⚖️ NEXORA: Judge Evaluation Guide

This guide is designed for judges of the **magicpin AI Challenge** to evaluate the **NEXORA** engine. It outlines step-by-step procedures to run, verify, and grade NEXORA's endpoints, robustness, and conversational compliance, based on the official challenge testing briefs.

> [!IMPORTANT]
> ### 🌐 NEXORA Deployed Production Links
> 
> * **⚡ Deployed Backend Engine (API):** [https://nexora-studio-0aaz.onrender.com/](https://nexora-studio-0aaz.onrender.com/) *(Health Endpoint: `/v1/healthz`)*
> * **🖥️ Live Operations Dashboard (UI):** [https://nexorabot-ai.vercel.app/](https://nexorabot-ai.vercel.app/)
> 
> | Environment | Backend Endpoint | Frontend Dashboard |
> | :--- | :--- | :--- |
> | **☁️ Live Production** | `https://nexora-studio-0aaz.onrender.com/` | `https://nexorabot-ai.vercel.app/` |
> | **💻 Local Development** | `http://localhost:8080` | `http://localhost:3000` |

## 📋 Prerequisites & Local Setup

Ensure the following tools are installed on your host system:

| Tool | Version | Purpose |
| :--- | :--- | :--- |
| **Docker** | 20.10+ | Containerized execution environment. |
| **Docker Compose** | 2.0+ | Multicontainer orchestration. |
| **cURL / HTTPie** | Any | Executing manual HTTP test requests. |
| **Python** | 3.11+ | Running local scripts (if not using Docker). |

### Create Environment Configuration
Create a `.env` file in the project root directory and specify your Groq API key:
```env
GROQ_API_KEY=gsk_your_real_groq_api_key_here
```

### Start the Service Stack
To launch the complete application stack (FastAPI backend, Next.js frontend, MongoDB, and Redis):
```bash
docker compose up --build
```
*Wait approximately 15 seconds for datastore health checks to pass and pre-seeding pipelines to complete.*

### Set target BOT_URL Endpoint
Before running the curl examples below, set the target bot endpoint based on the testing environment:

*   **Live Deployed Production Engine:**
    *   **Bash/zsh (Linux/macOS):** `export BOT_URL=https://nexora-studio-0aaz.onrender.com`
    *   **PowerShell (Windows):** `$BOT_URL="https://nexora-studio-0aaz.onrender.com"`
*   **Local Development Server:**
    *   **Bash/zsh (Linux/macOS):** `export BOT_URL=http://localhost:8080`
    *   **PowerShell (Windows):** `$BOT_URL="http://localhost:8080"`


## ⚡ Quick Evaluation Checklist

1.  [ ] **Run System:** Start the containers via `docker compose up --build`.
2.  [ ] **Verify Health:** Send `GET /v1/healthz` (ensure all DB connections are active and contexts preloaded).
3.  [ ] **Metadata Inspection:** Send `GET /v1/metadata` to verify submission information and author links.
4.  [ ] **Context Push (Phase 1):** Ingest test contexts and verify idempotency.
5.  [ ] **Tick Run (Phase 2):** Send `POST /v1/tick` to generate proactive actions.
6.  [ ] **Conversation Check (Phase 3):** Send `POST /v1/reply` to verify conversational state machine, auto-replies, and intents.
7.  [ ] **Decision Explainer:** Query `GET /v1/action/{id}/explain` to audit AI logic.

## 🚀 Phase-by-Phase Evaluation Guide

### Phase 1: Context Ingestion (`POST /v1/context`)

The judge harness sends context updates to ingest category vertical rules, merchant profiles, customer aggregates, and trigger events.

#### Test Context Ingestion
Submit a custom category context to the system:
```bash
curl -s -X POST $BOT_URL/v1/context \
  -H "Content-Type: application/json" \
  -d '{
    "scope": "category",
    "context_id": "wellness_clinics",
    "version": 1,
    "payload": {
      "slug": "wellness_clinics",
      "voice": {
        "tone": "supportive",
        "register": "friendly-peer",
        "vocab_allowed": ["health", "remedy", "consult"],
        "vocab_taboo": ["cheap", "discount", "guarantee"]
      },
      "peer_stats": {
        "avg_ctr": 0.052,
        "avg_rating": 4.5
      },
      "seasonal_beats": [],
      "digest": [],
      "trend_signals": []
    },
    "delivered_at": "2026-06-27T12:00:00Z"
  }'
```

**Expected Response:**
```json
{
  "accepted": true,
  "ack_id": "ack_wellness_clinics_v1",
  "stored_at": "2026-06-27T12:00:05.123Z",
  "processing_ms": 15.2
}
```

#### Test Version Control (Idempotency)
Re-submit the exact same context request. The server must reject it since version `1` is already saved:
```bash
curl -s -X POST $BOT_URL/v1/context \
  -H "Content-Type: application/json" \
  -d '{
    "scope": "category",
    "context_id": "wellness_clinics",
    "version": 1,
    "payload": {},
    "delivered_at": "2026-06-27T12:00:00Z"
  }'
```

**Expected Response:**
```json
{
  "accepted": false,
  "reason": "stale_version",
  "current_version": 1,
  "processing_ms": 1.2
}
```

### Phase 2: Proactive Engagement Actions (`POST /v1/tick`)

The judge harness triggers periodic tick events, providing active trigger IDs. The bot evaluates the triggers, prioritizes them, and generates engagement messages.

#### Test Tick Evaluation
Send a tick payload evaluating preloaded trigger `trg_001` (a `research_digest` trigger for merchant `m_001`):
```bash
curl -s -X POST $BOT_URL/v1/tick \
  -H "Content-Type: application/json" \
  -d '{
    "now": "2026-06-27T12:00:00Z",
    "available_triggers": ["trg_001"]
  }'
```

**Expected Response:**
```json
{
  "actions": [
    {
      "conversation_id": "conv_m_001_trg_001",
      "merchant_id": "m_001",
      "customer_id": null,
      "send_as": "nexora",
      "trigger_id": "trg_001",
      "template_name": "research_digest_template",
      "template_params": ["Arjun", "Dental Research Update", "cleaning"],
      "body": "Dr. Arjun, a recent clinical trial details how consistent fluoride treatments reduced adult dental caries by 38%. I've prepared a draft message for your high-risk patients. Would you like to review it?",
      "cta": "binary_yes_no",
      "suppression_key": "sup_research_m_001",
      "rationale": "Anchored on recent clinical digest item. Proposing patient campaign workflow utilizing commitment lever.",
      "priority_score": 75,
      "priority_rank": 1,
      "trigger_kind": "research_digest",
      "urgency": 3,
      "expires_at": "2026-07-15T00:00:00Z"
    }
  ],
  "processing_ms": 320.5
}
```

#### Test Suppression (Production Mode)
By default, the server runs in **Demo Mode** (`DEMO_MODE=true` in `.env`), which bypasses suppression for easy testing. To test production suppression:
1. Set `DEMO_MODE=False` in `.env` and restart your uvicorn/Docker container.
2. Send the `POST /v1/tick` request above. An action is returned.
3. Send the same `POST /v1/tick` request again. The response actions array will be empty (`[]`) because the trigger is suppressed in Redis for 7 days.

### Phase 3: Conversational Turn Handling (`POST /v1/reply`)

Handles conversation replies from merchants/customers, evaluating auto-replies, opt-outs, intent transitions, and language.

#### Test Intent Transition to Action Mode
Send a reply containing a positive commitment signal ("Yes"):
```bash
curl -s -X POST $BOT_URL/v1/reply \
  -H "Content-Type: application/json" \
  -d '{
    "conversation_id": "conv_m_001_trg_001",
    "merchant_id": "m_001",
    "customer_id": null,
    "from_role": "merchant",
    "message": "Yes, send the draft check list.",
    "received_at": "2026-06-27T12:05:00Z",
    "turn_number": 2
  }'
```

**Expected Response:**
The system transitions the prompt from discovery mode to action mode, returning the final campaign checklist:
```json
{
  "action": "send",
  "body": "Here is the checklist I drafted: 1. Identify patients with 2+ visits. 2. Send fluoride benefit overview. 3. Propose appointment booking. Ready to launch?",
  "cta": "binary_confirm_cancel",
  "rationale": "Merchant provided explicit commitment signal. Switched to action mode to deliver the requested checklist.",
  "processing_ms": 210.3
}
```

#### Test Hostile Opt-Out (Stop Keyword)
Verify that the bot politely handles stop requests and immediately terminates conversation threads:
```bash
curl -s -X POST $BOT_URL/v1/reply \
  -H "Content-Type: application/json" \
  -d '{
    "conversation_id": "conv_m_001_trg_001",
    "merchant_id": "m_001",
    "from_role": "merchant",
    "message": "Stop messaging me. Not interested.",
    "received_at": "2026-06-27T12:10:00Z",
    "turn_number": 3
  }'
```

**Expected Response:**
```json
{
  "action": "send",
  "body": "Apologies for the interruption. I won't message again. If anything changes, just reply 'Hi Nexora'. 🙏",
  "cta": "none",
  "rationale": "Merchant explicitly opted out. Sending polite exit and closing.",
  "processing_ms": 150.2
}
```

#### Test Auto-Reply Mitigation (Strike Counter)
Send consecutive canned auto-replies (e.g. "Thank you for contacting us..."):
*   **Strike 1:** The bot sends a gentle nudging reminder asking for human input.
*   **Strike 2:** The bot locks the thread for 24 hours (`action: wait`).
*   **Strike 3:** The bot marks the thread as ended (`action: end`).

## 🔎 Inspection, Resetting & Diagnostics

### Audit AI Decision Rationale
Explain why a specific action was chosen, which metrics were extracted from context, and what compulsion levers were used:
```bash
curl -s $BOT_URL/v1/action/conv_m_001_trg_001/explain
```

### Reset Demo Suppressions
To wipe suppressions and wait states during testing without deleting database contexts:
```bash
curl -s -X POST $BOT_URL/v1/demo/reset
```

### Full Teardown
To wipe all contexts, conversations, and logs from the datastores (called between grading windows):
```bash
curl -s -X POST $BOT_URL/v1/teardown
```

## 🛡️ Robustness & Error Testing

Verify the FastAPI exception handlers return structured JSON envelopes under crash conditions.

### Test Malformed JSON (returns HTTP 400)
```bash
curl -s -X POST $BOT_URL/v1/tick \
  -H "Content-Type: application/json" \
  -d '{"now": "2026-06-27T12:00:00Z", "available_triggers": ["trg_001"'
```

**Response:**
```json
{
  "success": false,
  "accepted": false,
  "reason": "invalid_json",
  "error": {
    "code": "INVALID_JSON",
    "message": "Request body contains malformed JSON."
  }
}
```

### Test Invalid Scope Parameter (returns HTTP 400)
```bash
curl -s -X POST $BOT_URL/v1/context \
  -H "Content-Type: application/json" \
  -d '{
    "scope": "invalid_scope_name",
    "context_id": "trg_rec_001",
    "version": 1,
    "payload": {},
    "delivered_at": "2026-06-27T12:00:00Z"
  }'
```

**Response:**
```json
{
  "success": false,
  "accepted": false,
  "reason": "invalid_scope",
  "details": "scope must be one of ['category', 'customer', 'merchant', 'trigger']",
  "error": {
    "code": "BAD_REQUEST",
    "message": "scope must be one of ['category', 'customer', 'merchant', 'trigger']"
  }
}
```

### Test Missing Trigger Context (returns HTTP 404)
```bash
curl -s -X POST $BOT_URL/v1/tick \
  -H "Content-Type: application/json" \
  -d '{
    "now": "2026-06-27T12:00:00Z",
    "available_triggers": ["trg_invalid_nonexistent"]
  }'
```

**Response:**
```json
{
  "success": false,
  "accepted": false,
  "reason": "trigger_not_found",
  "error": {
    "code": "TRIGGER_NOT_FOUND",
    "message": "Trigger 'trg_invalid_nonexistent' does not exist."
  }
}
```

## 🏃 Running Local Harness Simulations

To run the local grading simulator which mimics magicpin's official judge harness:

*   **From the Project Root:**
    *   **Local Backend:**
        ```bash
        python3 judge_simulator.py --bot-url http://localhost:8080 --groq-api-key $GROQ_API_KEY
        ```
    *   **Live Deployed Production Backend:**
        ```bash
        python3 judge_simulator.py --bot-url https://nexora-studio-0aaz.onrender.com --groq-api-key $GROQ_API_KEY
        ```

To expand the seed dataset files and generate the `expanded` data directory:

*   **From the Project Root:**
    ```bash
    python dataset/generate_dataset.py --seed-dir dataset --out expanded
    ```

*   **From the `backend/` Directory (PowerShell/Bash):**
    ```bash
    python ../dataset/generate_dataset.py --seed-dir ../dataset --out ../expanded
    ```

*   **From the `backend/` Directory (Windows CMD):**
    ```cmd
    python ..\dataset\generate_dataset.py --seed-dir ..\dataset --out ..\expanded
    ```

To run the submission pipeline which verifies the 30 canonical triggers and saves the final submission output:

*   **From the Project Root:**
    ```bash
    python3 generate_submission.py --expanded-dir expanded --out submission.jsonl
    ```

*   **From the `backend/` Directory (PowerShell/Bash):**
    ```bash
    python ../generate_submission.py --expanded-dir ../expanded --out ../submission.jsonl
    ```

*   **From the `backend/` Directory (Windows CMD):**
    ```cmd
    python ..\generate_submission.py --expanded-dir ..\expanded --out ..\submission.jsonl
    ```

👉 **Next Steps:** Review the [API Reference Guide](/docs/05-api-reference.md) to inspect detailed schemas and payloads.
