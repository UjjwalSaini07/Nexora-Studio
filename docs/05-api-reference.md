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
  "redis_connected": true
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
  "redis_connected": true
}
```

### 📸 Screenshots
*(Add Postman healthz request and response here)*

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
  "project_description": "NEXORA: A production-grade merchant engagement engine designed for the magicpin AI Challenge. Automatically translates raw business database signals (categories, merchants, customers, triggers) into hyper-personalized, context-grounded, multi-turn conversational actions."
}
```

### 📸 Screenshots
*(Add Postman metadata response here)*

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
*(Add Postman context ingestion success and version stale response here)*

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
  "now": "2026-06-27T12:00:00Z",
  "available_triggers": ["trg_rec_001"]
}
```

#### Example Success Response
```json
{
  "actions": [
    {
      "conversation_id": "conv_m_salon_01_trg_rec_001",
      "merchant_id": "m_salon_01",
      "customer_id": "cust_salon_01",
      "send_as": "merchant_on_behalf",
      "trigger_id": "trg_rec_001",
      "template_name": "recall_due_template",
      "template_params": ["Priya", "hair spa appointment", "Saturday 2PM"],
      "body": "Hi Priya, it's been 3 months since your last hair spa. We have slots open this weekend on Saturday at 2PM or Sunday at 11AM. Would you like to book?",
      "cta": "multi_choice_slot",
      "suppression_key": "sup_recall_cust_salon_01",
      "rationale": "Identified customer recall eligibility. Utilized social specificity and slot options to prompt booking.",
      "priority_score": 85,
      "priority_rank": 1,
      "trigger_kind": "recall_due",
      "urgency": 4,
      "expires_at": "2026-07-10T12:00:00Z"
    }
  ],
  "processing_ms": 234.1
}
```

### 📸 Screenshots
*(Add Postman tick evaluation response here)*

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
  "conversation_id": "conv_m_salon_01_trg_rec_001",
  "merchant_id": "m_salon_01",
  "customer_id": "cust_salon_01",
  "from_role": "customer",
  "message": "Yes, Saturday 2PM works for me.",
  "received_at": "2026-06-27T12:05:00Z",
  "turn_number": 2
}
```

#### Example Success Response (Transition to Action Mode)
```json
{
  "action": "send",
  "body": "Perfect! I have blocked Saturday at 2:00 PM for your hair spa. See you at the salon!",
  "cta": "none",
  "rationale": "Customer responded positively indicating slot selection. Transitioned to execution mode and confirmed slot booking.",
  "processing_ms": 185.3
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
*(Add Postman reply state machine responses here)*

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
*(Add Postman teardown completion response here)*

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
*(Add Postman demo reset response here)*

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
  "conversation_id": "conv_m_salon_01_trg_rec_001",
  "trigger_id": "trg_rec_001",
  "why_selected": "Trigger 'trg_rec_001' of kind 'recall_due' with urgency 4 was selected and assigned a priority score of 85 (ranked #1).",
  "priority_breakdown": {
    "score": 85,
    "rank": 1,
    "reason": "score=85: [urgency=4/5 -> 20pts] + [expires_in=312.0h -> 0pts] + [kind=recall_due -> 18pts] + [source=internal -> 6pts] + [scope=customer -> 10pts] + [payload_keys=1 -> 2pts]"
  },
  "merchant_signals_used": ["high_lapsing"],
  "category_signals_used": [],
  "customer_signals_used": ["preferred_slots:evening"],
  "compulsion_levers_used": ["specificity", "commitment"],
  "confidence_score": 0.92,
  "suppression_status": {
    "is_suppressed": false,
    "suppression_key": "sup_recall_cust_salon_01"
  },
  "wait_state_status": {
    "is_waiting": false,
    "wait_until": null
  },
  "rationale": "Identified customer recall eligibility. Utilized social specificity and slot options to prompt booking."
}
```

### 📸 Screenshots
*(Add Postman explain response here)*

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
  "total_ticks": 450,
  "total_actions": 380,
  "total_replies": 1200,
  "avg_processing_ms": 210.5,
  "active_conversations": 32,
  "redis_suppressions_active": 45
}
```

### 📸 Screenshots
*(Add Postman dashboard stats response here)*

👉 **Next Steps:** Proceed to the [Judge Evaluation Guide](/docs/06-judge-testing-guide.md) to run manual test queries.
