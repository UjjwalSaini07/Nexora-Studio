# 📡 NEXORA: API Reference

This document provides a comprehensive reference of all public endpoints exposed by the NEXORA backend, including step-by-step Postman testing guidelines.

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

## 📋 Endpoints Overview

| Method | Path | Auth Required | Purpose |
| :--- | :--- | :--- | :--- |
| **`GET`** | `/v1/healthz` | No | Liveness and health probe. |
| **`GET`** | `/v1/metadata` | Optional | Team details and system configuration. |
| **`POST`** | `/v1/context` | Optional | Ingest category, merchant, customer, or trigger data. |
| **`POST`** | `/v1/tick` | Optional | Process active triggers and generate engagement actions. |
| **`POST`** | `/v1/reply` | Optional | Process conversational turns and reply logic. |
| **`POST`** | `/v1/teardown` | No | Reset the database state (called between test windows). |
| **`POST`** | `/v1/demo/reset` | Optional | Reset demo-specific runtime state. |
| **`GET`** | `/v1/action/{conversation_id}/explain` | Optional | Explain the decision logic behind an action. |
| **`GET`** | `/v1/dashboard/contexts` | Optional | Retrieve list of ingested contexts. |
| **`GET`** | `/v1/dashboard/actions` | Optional | Fetch recent composed tick actions. |
| **`GET`** | `/v1/dashboard/replies` | Optional | Fetch recent message turn replies. |
| **`GET`** | `/v1/dashboard/stats` | Optional | Fetch execution metrics and statistics. |

## 🔐 Authentication

If authentication is enabled via the environment (`ENABLE_AUTH=true`), all routes marked as **Optional** require a shared secret Bearer Token in the HTTP headers:

```http
Authorization: Bearer <API_AUTH_TOKEN>
```

## 🛡️ Rate Limiting

The API implements three layers of rate limiting to protect the system and maintain SLA compliance:
1.  **Global Client Limit:** 1,200 requests per minute per IP address.
2.  **Endpoint Limit:** 100 requests per minute per IP address for any single endpoint.
3.  **Conversation Limit:** 10 requests per minute per `conversation_id` on the `/v1/reply` endpoint.

> [!NOTE]
> `/v1/healthz` is exempt from all rate limiting to prevent false negatives on health checkers.

## ❌ Global Error Handling Schema

Every endpoint returns a structured JSON payload in case of validation failures, authorization issues, or internal exceptions. The error structure is defined as follows:

```json
{
  "success": false,
  "accepted": false,
  "reason": "error_reason_slug",
  "error": {
    "code": "ERROR_CODE_SLUG",
    "message": "Human-readable explanation of the error.",
    "details": null
  }
}
```

### 📋 Standard Error Codes

| HTTP Status | Error Code | Reason | Description |
| :--- | :--- | :--- | :--- |
| **`400`** | `INVALID_JSON` | `invalid_json` | The request body contains malformed JSON. |
| **`400`** | `BAD_REQUEST` | `invalid_scope` | An invalid scope was provided (e.g., in context push). |
| **`401`** | `UNAUTHORIZED` | `unauthorized` | Missing or invalid authentication token. |
| **`404`** | `TRIGGER_NOT_FOUND` | `trigger_not_found` | The requested trigger ID does not exist in MongoDB. |
| **`404`** | `MERCHANT_NOT_FOUND` | `merchant_not_found` | The specified merchant ID does not exist in MongoDB. |
| **`404`** | `CUSTOMER_NOT_FOUND` | `customer_not_found` | The specified customer ID does not exist in MongoDB. |
| **`413`** | `PAYLOAD_TOO_LARGE` | `payload_too_large` | The request payload exceeds size limits. |
| **`422`** | `VALIDATION_ERROR` | `validation_error` | Request parameters failed Pydantic model validation. |
| **`429`** | `RATE_LIMIT_EXCEEDED`| `rate_limit_exceeded`| The rate limit threshold has been exceeded. |
| **`500`** | `INTERNAL_ERROR` | `internal_error` | An unexpected exception occurred inside the application. |

## 🛠️ Endpoint Specifications & Postman Testing Guide

### 🚀 Setup Postman Environment
Before testing, add these variables to your Postman Environment:
*   `base_url`: `http://localhost:8080` (Local Dev)
*   `base_url`: `https://nexora-studio-0aaz.onrender.com` (Deployed Live Production)
*   `auth_token`: `your_configured_bearer_token` (only required if `ENABLE_AUTH=true`)

### 1. `GET /v1/healthz`

Returns the operational status of the service, uptime, and database connectivity.

#### Postman Setup
*   **Method:** `GET`
*   **URL:** `{{base_url}}/v1/healthz`
*   **Headers:** *None*
*   **Body:** *None (Select "none" in Postman body)*

#### Response Parameters
*   `status`: Status of the server (`"ok"`, `"degraded"`, `"down"`).
*   `uptime_seconds`: Time in seconds since the process was started.
*   `contexts_loaded`: Object displaying context document counts in cache by scope.
*   `mongo_connected`: Boolean indicating MongoDB connectivity.
*   `redis_connected`: Boolean indicating Redis connectivity.
*   `total_actions_logged`: Total proactive merchant engagement actions stored in MongoDB.
*   `total_replies_logged`: Total multi-turn replies logged in MongoDB.
*   `active_suppression_keys`: Total active suppression keys in the database.
*   `system_start_time`: ISO UTC timestamp indicating when the bot engine booted.
*   `environment`: Active running environment (`"production"` or `"development"`).
*   `memory_usage_mb`: Current container memory utilization in MB (Linux only, returns null on Windows).

#### Example Success Response
```json
{
  "status": "ok",
  "uptime_seconds": 1500,
  "contexts_loaded": {
    "category": 5,
    "merchant": 50,
    "customer": 200,
    "trigger": 100
  },
  "mongo_connected": true,
  "redis_connected": true,
  "total_actions_logged": 42,
  "total_replies_logged": 18,
  "active_suppression_keys": 4,
  "system_start_time": "2026-06-28T16:55:00Z",
  "environment": "production",
  "memory_usage_mb": 42.12
}
```

#### Example Degraded Response
If Redis or MongoDB experiences a transient outage, the endpoint returns a `200 OK` status with `status: "degraded"` to avoid triggering automatic restarts:
```json
{
  "status": "degraded",
  "uptime_seconds": 1500,
  "contexts_loaded": {
    "category": 0,
    "merchant": 0,
    "customer": 0,
    "trigger": 0
  },
  "mongo_connected": false,
  "redis_connected": true,
  "total_actions_logged": 0,
  "total_replies_logged": 0,
  "active_suppression_keys": 0,
  "system_start_time": "2026-06-28T16:55:00Z",
  "environment": "production",
  "memory_usage_mb": null
}
```

### 📸 Screenshots
<img width="1577" height="1037" alt="image" src="https://github.com/user-attachments/assets/45c17790-2295-4d5e-bd76-d9bf299a7b9a" />

### 2. `GET /v1/metadata`

Provides metadata about the submission, team structure, and system approach.

#### Postman Setup
*   **Method:** `GET`
*   **URL:** `{{base_url}}/v1/metadata`
*   **Headers:**
    *   `Authorization`: `Bearer {{auth_token}}` (if authentication is enabled)
*   **Body:** *None*

#### Example Success Response
```json
{
  "team_name": "NEXORA Engine",
  "team_members": ["Ujjwal Saini"],
  "model": "llama-3.3-70b-versatile",
  "approach": "4-context composition engine: trigger-kind dispatch -> specialized prompt registers -> Groq Llama (T=0) -> output validation + anti-repetition. Conversational states driven by a dedicated state machine.",
  "contact_email": "ujjwalsaini0007@gmail.com",
  "version": "1.0.0",
  "submitted_at": "2026-06-25T08:00:00Z",
  "author_portfolio": "https://ujjwalsaini.vercel.app",
  "author_github": "https://github.com/UjjwalSaini07",
  "project_description": "NEXORA: A production-grade merchant engagement engine designed for the magicpin AI Challenge. Automatically translates raw business database signals (categories, merchants, customers, triggers) into hyper-personalized, context-grounded, multi-turn conversational actions.",
  "llm_fallback_model": "llama-3.1-8b-instant",
  "sla_time_budget": "30s SLA (with a 22s LLM hard timeout)",
  "hot_cache_type": "Redis hot cache (supressions, wait-states, turn counters)",
  "durable_store_type": "MongoDB (context registry, action audit logs, reply history)",
  "production_link": "https://nexora-studio-0aaz.onrender.com/",
  "frontend_dashboard_link": "https://nexorabot-ai.vercel.app/"
}
```

### 📸 Screenshots
<img width="1567" height="1002" alt="image" src="https://github.com/user-attachments/assets/34483acf-7f91-4928-9f16-0b9fc6c34c40" />

### 3. `POST /v1/context`

Ingests or updates context data in the system.

#### Postman Setup
*   **Method:** `POST`
*   **URL:** `{{base_url}}/v1/context`
*   **Headers:**
    *   `Content-Type`: `application/json`
    *   `Authorization`: `Bearer {{auth_token}}` (if authentication is enabled)
*   **Body (raw JSON):**
```json
{
  "scope": "trigger",
  "context_id": "trg_rec_001",
  "version": 2,
  "payload": {
    "id": "trg_rec_001",
    "kind": "recall_due",
    "urgency": 4,
    "scope": "customer",
    "source": "internal",
    "merchant_id": "m_salon_01",
    "customer_id": "cust_salon_01",
    "suppression_key": "sup_recall_cust_salon_01",
    "expires_at": "2026-07-10T12:00:00Z",
    "payload": {
      "available_slots": ["Saturday 2PM", "Sunday 11AM"]
    }
  },
  "delivered_at": "2026-06-27T10:00:00Z"
}
```

#### Example Success Response
```json
{
  "accepted": true,
  "ack_id": "ack_trg_rec_001_v2",
  "stored_at": "2026-06-27T10:00:05.123Z",
  "processing_ms": 12.4
}
```

#### Example Stale Version Response
If the version pushed is less than or equal to the version cached, the update is rejected as stale:
```json
{
  "accepted": false,
  "reason": "stale_version",
  "current_version": 2,
  "processing_ms": 1.8
}
```

### 📸 Screenshots
### Push Trigger Context
<img width="1572" height="997" alt="image" src="https://github.com/user-attachments/assets/abc18d2e-6b58-4505-b8f4-a086d3736a25" />

### Category Context
<img width="1567" height="997" alt="image" src="https://github.com/user-attachments/assets/dcb223b6-ceaf-42ac-b8c2-6af38ed63c32" />

### Merchant Context
<img width="1577" height="992" alt="image" src="https://github.com/user-attachments/assets/c9b1a75b-c329-4e3b-adca-b54711ab6240" />

### 4. `POST /v1/tick`

Evaluates triggers and returns the corresponding engagement actions.

#### Postman Setup
*   **Method:** `POST`
*   **URL:** `{{base_url}}/v1/tick`
*   **Headers:**
    *   `Content-Type`: `application/json`
    *   `Authorization`: `Bearer {{auth_token}}` (if authentication is enabled)
*   **Body (raw JSON):**
```json
{
  "now": "2026-04-29T10:30:00Z",
  "available_triggers": [
    "trg_018_supply_atorvastatin_recall"
  ]
}
```

#### Example Success Response
```json
{
    "actions": [
        {
            "conversation_id": "conv_m_009_apollo_pharmacy_jaipur_supply_alert",
            "merchant_id": "m_009_apollo_pharmacy_jaipur",
            "send_as": "nexora",
            "trigger_id": "trg_018_supply_atorvastatin_recall",
            "template_name": "nexora_supply_alert_v1",
            "template_params": [
                "Ramesh",
                "atorvastatin",
                "AT2024-1102"
            ],
            "body": "Ramesh ji, atorvastatin ki voluntary recall hai - batches AT2024-1102 aur AT2024-1108. Aapke 24 high-risk adult customers ismein shaamil hain. Main customer WhatsApp aur replacement pickup workflow draft karoon?",
            "cta": "binary_yes_no",
            "suppression_key": "alert:atorvastatin:2026-04",
            "rationale": "The trigger is a high-urgency supply alert for atorvastatin, and the compulsion lever used is specificity/verifiability with the exact batch numbers and the number of affected customers, along with a clear call-to-action for drafting a customer WhatsApp and replacement pickup workflow.",
            "priority_score": 72,
            "priority_rank": 1,
            "trigger_kind": "supply_alert",
            "urgency": 5,
            "expires_at": "2026-05-30T00:00:00Z"
        }
    ],
    "processing_ms": 2697.74
}
```

### 📸 Screenshots
<img width="1570" height="995" alt="image" src="https://github.com/user-attachments/assets/6dbdd373-21f7-4fc6-bf00-998ecb1593b0" />

### 5. `POST /v1/reply`

Processes conversational replies and executes multi-turn decision state transitions.

#### Postman Setup
*   **Method:** `POST`
*   **URL:** `{{base_url}}/v1/reply`
*   **Headers:**
    *   `Content-Type`: `application/json`
    *   `Authorization`: `Bearer {{auth_token}}` (if authentication is enabled)
*   **Body (raw JSON):**
```json
{
  "conversation_id":"conv_m_009_apollo_pharmacy_jaipur_supply_alert",
  "from_role":"merchant",
  "message":"Yes",
  "turn_number":2,
  "received_at":"2026-04-29T10:31:00Z"
}
```

#### Example Success Response (Transition to Action Mode)
```json
{
    "action": "send",
    "body": "Let's draft the agreement then",
    "cta": "Please provide the necessary details",
    "rationale": "Merchant has shown interest, time to move forward with the agreement",
    "processing_ms": 1042.51
}
```

#### Example Wait State Response
If consecutive auto-replies are received, the handler tells the gateway to wait:
```json
{
  "action": "wait",
  "wait_seconds": 86400,
  "rationale": "Auto-reply detected twice consecutively. Placing conversation in wait state for 24 hours.",
  "processing_ms": 4.2
}
```

### 📸 Screenshots
<img width="1571" height="1002" alt="image" src="https://github.com/user-attachments/assets/2afd215c-39c1-439d-812d-23d31326f738" />

### 6. `POST /v1/teardown`

Wipes all database state from Redis and MongoDB. **Exempt from authentication.**

#### Postman Setup
*   **Method:** `POST`
*   **URL:** `{{base_url}}/v1/teardown`
*   **Headers:** *None*
*   **Body:** *None*

#### Example Success Response
```json
{
  "success": true,
  "deleted": {
    "contexts": 255,
    "conversations": 12,
    "actions_log": 45,
    "replies_log": 90,
    "ticks_log": 12,
    "suppressions_log": 14,
    "contexts_history": 255
  },
  "redis_keys_deleted": 421
}
```

### 📸 Screenshots
<img width="1581" height="1002" alt="image" src="https://github.com/user-attachments/assets/08953647-17f0-450d-ab45-abee2fb102ac" />

### 7. `POST /v1/demo/reset`

Clears dynamic demonstration runtime artifacts (suppression, wait states, active conversational states) without deleting database contexts.

#### Postman Setup
*   **Method:** `POST`
*   **URL:** `{{base_url}}/v1/demo/reset`
*   **Headers:**
    *   `Authorization`: `Bearer {{auth_token}}` (if authentication is enabled)
*   **Body:** *None*

#### Example Success Response
```json
{
  "success": true,
  "suppression_keys_removed": 14,
  "wait_states_removed": 2,
  "conversation_states_removed": 5,
  "message": "Demo state reset successfully."
}
```

### 📸 Screenshots
<img width="1575" height="1007" alt="image" src="https://github.com/user-attachments/assets/8ca109b2-a2a2-42de-b5d8-a436f3860980" />

### 8. `GET /v1/action/{conversation_id}/explain`

Generates diagnostic rationale explaining the specific triggers, levers, and signals selected for a given conversation.

#### Postman Setup
*   **Method:** `GET`
*   **URL:** `{{base_url}}/v1/action/conv_m_salon_01_trg_rec_001/explain`
*   **Headers:**
    *   `Authorization`: `Bearer {{auth_token}}` (if authentication is enabled)
*   **Body:** *None*

#### Example Success Response
```json
{
    "conversation_id": "conv_m_010_sunrisepharm_pharmacy_lucknow_gbp_unverified",
    "trigger_id": "trg_021_unverified_gbp_sunrise",
    "why_selected": "Trigger 'trg_021_unverified_gbp_sunrise' of kind 'gbp_unverified' with urgency 3 was selected and assigned a priority score of 47 (ranked #1).",
    "priority_breakdown": {
        "score": 47,
        "rank": 1,
        "reason": "score=47: [urgency=3/5 → 15pts] + [expires_in=733.5h → 0pts] + [kind=gbp_unverified → 9pts] + [source=internal → 6pts] + [scope=merchant → 7pts] + [payload_keys=10 → 10pts]"
    },
    "merchant_signals_used": [
        "unverified_gbp",
        "no_active_offers",
        "no_recent_conversation",
        "delivery_not_set_up"
    ],
    "category_signals_used": [
        "summer surge — ORS, sunscreen, anti-fungal, deodorant",
        "monsoon — anti-bacterial, anti-fungal, immunity supplements peak",
        "festival sweets → blood sugar spike — diabetic monitoring needs surge",
        "respiratory peak — cough/cold/anti-allergic 2x baseline",
        "medicine home delivery",
        "generic medicine",
        "diabetes care kit",
        "blood pressure monitor"
    ],
    "customer_signals_used": [],
    "compulsion_levers_used": [
        "urgency",
        "deadline",
        "specificity"
    ],
    "confidence_score": 0.86,
    "suppression_status": {
        "is_suppressed": true,
        "suppression_key": "unverified:m_010"
    },
    "wait_state_status": {
        "is_waiting": false,
        "wait_until": null
    },
    "rationale": "The signal driving this message is the unverified Google Business Profile, which can lead to reduced visibility and lost customers. The compulsion lever used is the estimated 30% uplift in views upon verification, making it a clear and bounded action with a known time cost.",
    "trigger_ranking_details": {
        "score": 47,
        "rank": 1,
        "reason": "score=47: [urgency=3/5 → 15pts] + [expires_in=733.5h → 0pts] + [kind=gbp_unverified → 9pts] + [source=internal → 6pts] + [scope=merchant → 7pts] + [payload_keys=10 → 10pts]"
    }
}
```

### 📸 Screenshots
<img width="1566" height="997" alt="image" src="https://github.com/user-attachments/assets/8fe0c4c9-b678-481b-b3c7-853077689a41" />

### 9. `GET /v1/dashboard/stats`

Retrieves summary performance metrics, throughput, and error ratios.

#### Postman Setup
*   **Method:** `GET`
*   **URL:** `{{base_url}}/v1/dashboard/stats`
*   **Headers:**
    *   `Authorization`: `Bearer {{auth_token}}` (if authentication is enabled)
*   **Body:** *None*

#### Example Success Response
```json
{
    "bot_status": "running",
    "mongo_connected": true,
    "redis_connected": true,
    "llm_status": "configured",
    "contexts_loaded": {
        "category": 5,
        "merchant": 50,
        "customer": 200,
        "trigger": 100
    },
    "today_messages": 228,
    "active_conversations": 10,
    "pending_replies": 10,
    "suppressed_messages": 5,
    "average_decision_confidence": 0.91,
    "top_trigger": "recall_due",
    "top_category": "dentists",
    "top_merchant": "m_001_drmeera_dentist_delhi",
    .........so on
```

### 📸 Screenshots
<img width="1576" height="1007" alt="image" src="https://github.com/user-attachments/assets/535c75fc-2296-4dcf-bc80-750c28c27d8c" />

👉 **Next Steps:** Proceed to the [Judge Evaluation Guide](/docs/06-judge-testing-guide.md) to run manual test queries.
