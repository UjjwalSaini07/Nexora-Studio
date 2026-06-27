# NEXORA — magicpin AI Challenge Submission

NEXORA is a production-grade merchant engagement bot built for the magicpin
AI Challenge. It receives structured context about merchants, customers,
and categories, decides what to say and when, and composes specific,
on-brand WhatsApp messages via an LLM (Groq) — all behind a versioned,
idempotent HTTP API that matches the official challenge contract exactly.

**Team:** NEXORA Engine · **Stack:** FastAPI + MongoDB + Redis + Groq (Llama) + Next.js

## Table of contents

1. [Architecture](#architecture)
2. [Quick start (Docker)](#quick-start-docker)
3. [Quick start (without Docker)](#quick-start-without-docker)
4. [Environment variables](#environment-variables)
5. [API reference](#api-reference)
6. [Dataset](#dataset)
7. [Testing](#testing)
8. [Frontend dashboard](#frontend-dashboard)
9. [Deployment](#deployment)
10. [Submission format note](#submission-format-note)
11. [Project structure](#project-structure)
12. [Requirements checklist](#requirements-checklist)


## Architecture

```
                    ┌─────────────────────────────────────────────────────┐
                    │              magicpin Judge Harness                 │
                    │   (LLM playing merchant + context injector + scorer)│
                    └──────────────────────────┬──────────────────────────┘
                                                │ HTTP/JSON
                                                ▼
┌──────────────────────────────────────────────────────────────────────────────┐
│                         NEXORA Bot Server (FastAPI)                            │
│                                                                               │
│  /v1/healthz  /v1/metadata  /v1/context  /v1/tick  /v1/reply  /v1/teardown  │
│                                          │                  │                │
│                          ┌───────────────▼──────────────────▼─────────────┐ │
│                          │         Context Store Layer                    │ │
│                          │  Redis: version index + suppression keys      │ │
│                          │  MongoDB: full context payloads + audit log   │ │
│                          └────────────────┬────────────────────────────── ┘ │
│                                           │                                  │
│                          ┌────────────────▼─────────────────────────────┐  │
│                          │     EngagementComposer (core logic)          │  │
│                          │  TriggerRouter → ContextAssembler →          │  │
│                          │  PromptBuilder → Groq LLM → OutputValidator  │  │
│                          └────────────────┬─────────────────────────────┘  │
│                                           │                                  │
│                          ┌────────────────▼─────────────────────────────┐  │
│                          │   ReplyHandler (multi-turn state machine)    │  │
│                          │  Auto-reply detector · Intent router ·       │  │
│                          │  Language detector · Graceful exit logic     │  │
│                          └───────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────────────────────────────────┘
                                           │
                          ┌────────────────▼───────────────────────────────┐
                          │      Next.js Operations Dashboard (port 3000) │
                          │  Live monitor · Conversations · Contexts ·    │
                          │  Simulator runner · Score analytics           │
                          └─────────────────────────────────────────────────┘
```

**Why Groq:** the 30-second response budget (and the need to compose up
to 20 actions per `/v1/tick` call) rewards low-latency inference. Groq's
LPU-backed hosting of Llama 3.3 70B gives us full-size-model quality at a
fraction of typical inference latency, with `llama-3.1-8b-instant` as an
automatic fallback if the primary model errors out.


## Quick start (Docker)

This is the fastest path to a fully running stack (Mongo + Redis + backend + frontend).

```bash
git clone <this-repo>
cd nexora-bot
cp .env.example .env
# Edit .env and set GROQ_API_KEY (get one free at https://console.groq.com/keys)

docker compose up --build
```

This will:
1. Start MongoDB and Redis
2. Build the backend image, **generating the expanded dataset inside the
   image** (deterministic — same seed, same output every time)
3. Start the backend on `http://localhost:8080`
4. Build and start the frontend dashboard on `http://localhost:3000`

Verify it's healthy:

```bash
curl http://localhost:8080/v1/healthz
# {"status":"ok","uptime_seconds":12,"contexts_loaded":{"category":5,"merchant":50,"customer":200,"trigger":100},...}
```

Open `http://localhost:3000` for the live operations dashboard.


## Quick start (without Docker)

### Backend

```bash
cd backend
cp .env.example .env
# Edit .env: set GROQ_API_KEY, and MONGO_URI/REDIS_URL if not running locally

pip install -r requirements.txt

# You need a local MongoDB and Redis running. Quickest way on most systems:
#   redis-server --daemonize yes
#   mongod --dbpath /tmp/mongo-data &
# (or install via your OS package manager / Homebrew / apt)

# Generate the expanded dataset (50 merchants, 200 customers, 100 triggers, 30 test pairs)
python3 ../dataset/generate_dataset.py --seed-dir ../dataset --out ../expanded

uvicorn main:app --host 0.0.0.0 --port 8080 --reload
```

`uvicorn bot:app` also works — `backend/bot.py` is a thin alias for `main:app`,
provided because the official testing brief's reference skeleton names the
file `bot.py`. Both start the exact same application.

### Frontend

```bash
cd frontend
cp .env.example .env.local
npm install
npm run dev
```

Open `http://localhost:3000`.


## Environment variables

See `.env.example` (root, for docker-compose), `backend/.env.example`, and
`frontend/.env.example` for the full annotated list. The most important:

| Variable | Where | Purpose |
|---|---|---|
| `GROQ_API_KEY` | backend | Your Groq API key. Required for `/v1/tick` and `/v1/reply` to compose real messages. |
| `LLM_MODEL` | backend | Default `llama-3.3-70b-versatile`. |
| `LLM_FALLBACK_MODEL` | backend | Default `llama-3.1-8b-instant`, used if the primary model fails every retry. |
| `MONGO_URI` / `REDIS_URL` | backend | Datastore connection strings. |
| `TEAM_NAME` / `TEAM_MEMBERS` / `CONTACT_EMAIL` | backend | Returned by `/v1/metadata`. |
| `RATE_LIMIT_PER_MINUTE` | backend | Default `1200` — comfortably above the judge harness's documented 10 req/sec (600/min) ceiling, with headroom for warmup bursts. |
| `ENABLE_AUTH` / `API_AUTH_TOKEN` | backend | Optional shared-secret auth on `/v1/*` routes (off by default — the judge harness isn't guaranteed to send an Authorization header). |
| `NEXT_PUBLIC_BOT_URL` | frontend | Where the dashboard fetches data from. **Inlined at build time** — see note below. |

> **Frontend build-time URL note:** `NEXT_PUBLIC_BOT_URL` is inlined into
> the client JS bundle at build time (standard Next.js behavior for
> `NEXT_PUBLIC_*` vars). If you deploy the backend and frontend to different
> public URLs, rebuild the frontend image with the correct
> `NEXT_PUBLIC_BOT_URL` build arg pointing at your real backend URL.


## API reference

All 5 judge-facing endpoints plus an optional teardown endpoint, exactly per
`challenge-testing-brief.md`.

### `GET /v1/healthz`
Liveness probe. **Never returns a 500** — if Mongo or Redis is unreachable,
returns `200` with `status: "degraded"` and the relevant `*_connected: false`
flag, so the judge's "3 consecutive non-200 healthz" penalty is never
triggered by a transient backend hiccup.

```json
{"status":"ok","uptime_seconds":142,"contexts_loaded":{"category":5,"merchant":50,"customer":200,"trigger":100},"mongo_connected":true,"redis_connected":true}
```

### `GET /v1/metadata`
Team identity and approach summary, used by the judge for transparency.

### `POST /v1/context`
Versioned, idempotent context ingestion for `category` / `merchant` /
`customer` / `trigger` scopes. Same-or-older version → `accepted: false,
reason: "stale_version"`. Higher version → accepted and persisted.

### `POST /v1/tick`
Periodic wake-up. Composes up to `TICK_MAX_ACTIONS` (default 20) actions
for the given `available_triggers`, respecting suppression keys, expiry
(checked against the **simulated** `now` from the request, never real
wall-clock time — see the regression test for why this matters), and the
"max one action per `(merchant_id, conversation_id)` pair per tick" rule.

### `POST /v1/reply`
Handles one inbound turn of a conversation. Returns `send` / `wait` / `end`.
Detects WhatsApp Business auto-replies (1st → friendly nudge, 2nd → wait
24h, 3rd → end), hard-stop/opt-out language (graceful single exit message),
explicit commit signals (switches to drafting the actual artifact instead
of asking another qualifying question), and mid-conversation language
switches.

### `POST /v1/teardown` *(optional, called by the judge between test windows)*
Wipes all persisted Redis keys and Mongo documents. Idempotent, always
returns 200, never requires auth — per the privacy requirement that bots
must not retain context/conversation data after a test ends.

### Dashboard-support endpoints (`/v1/dashboard/*`)
Read-only endpoints backing the Next.js dashboard (`contexts`, `actions`,
`replies`, `conversations/{id}`, `stats`). Not part of the judge's 5
required endpoints — purely operational tooling.


## Dataset

```
dataset/
  categories/{dentists,salons,restaurants,gyms,pharmacies}.json   # official seed (unmodified)
  merchants_seed.json   customers_seed.json   triggers_seed.json   # official seeds (unmodified)
  generate_dataset.py                                              # official generator (unmodified)
expanded/        # generated: 50 merchants, 200 customers, 100 triggers, test_pairs.json (30 canonical pairs)
```

These are the **official** files from magicpin's challenge zip, used
as-is. Regenerate the expanded dataset anytime with:

```bash
python3 dataset/generate_dataset.py --seed-dir dataset --out expanded
```

`generate_submission.py` (repo root) drives the **real, running bot**
through all 30 canonical test pairs over its actual HTTP API and writes
`submission.jsonl`:

```bash
python3 generate_submission.py --bot-url http://localhost:8080 --dataset-dir expanded
```


## Testing

```bash
cd backend
pip install -r requirements.txt
pytest tests/ -v
```

**83 tests, all passing**, covering:
- Unit tests: output validation, auto-reply/intent/language detectors, prompt construction
- Integration tests: the real FastAPI app (via `httpx.AsyncClient` + `fakeredis` + `mongomock-motor`)
  exercised against the **real official dataset** — idempotency, suppression,
  customer-scope `send_as` correction, auto-reply-hell → wait → end, hostile
  message handling, intent transition
- Warmup-phase test matching `challenge-testing-brief.md` §4 Phase 1 exactly
  (255 base contexts reflected in `/v1/healthz`)
- All 30 canonical `test_pairs.json` pairs proven to produce a valid action
- Regression tests for two real bugs found via live end-to-end testing
  against the official dataset (see `tests/test_regressions.py`):
  1. The trigger-expiry check must compare against the judge's *simulated*
     `now` (from the `/v1/tick` request), never the real wall-clock time —
     since seed-dataset `expires_at` values are authored on the challenge's
     own simulated timeline.
  2. `/v1/healthz` must survive a Redis/Mongo ping exception and report
     `degraded`, never crash with a raw 500.

`backend/dev_tools/` contains two local-only test doubles (never used in
production): `mock_groq_server.py` (an OpenAI-compatible mock that parses
real prompt content for genuinely deterministic local testing) and
`run_sandbox_demo.py` (boots the real app against a real Redis + an
in-memory Mongo, for environments without a local MongoDB install).


## Frontend dashboard

Next.js 16 (App Router) + TypeScript + Tailwind v4. Five pages:

| Route | Purpose |
|---|---|
| `/` | Live ops overview — heartbeat-pulse status, context counts, action/CTA breakdown, recent actions feed |
| `/conversations` | Turn-by-turn conversation timelines, auto-reply badges, intent-transition markers |
| `/contexts` | Searchable inspector for every loaded context, by scope, with full JSON view |
| `/simulator` | Browser-driven health checks and tick runs against the live bot, with streamed output |
| `/scores` | Objective anti-pattern tracking (URLs, taboo words, missing fields) from the bot's own action log |

> The dashboard's `/scores` and `/simulator` pages do **not** reproduce
> magicpin's real 5-dimension LLM-judged scoring (that requires the
> judge's own model and is run via `judge_simulator.py`, not from this
> dashboard) — they're clearly labeled as operational/diagnostic tooling
> that complements, rather than replaces, the official judge.

```bash
cd frontend
npm install
npm run dev      # development
npm run build && npm run start   # production
```


## Deployment

Any host with a public HTTPS URL works. The bot is a standard FastAPI/
Uvicorn app with no platform-specific dependencies.

- **Railway / Render / Fly.io**: point at `backend/Dockerfile` (build
  context = repo root) or use `docker-compose.yml` directly if the
  platform supports compose.
- **Bare VM**: `docker compose up -d --build`, or run `uvicorn main:app`
  behind a reverse proxy (nginx/Caddy) with your own MongoDB/Redis.
- Make sure `GROQ_API_KEY` is set and the published port (8080) is
  reachable over HTTPS before submitting your bot URL via the challenge
  portal.


## Submission format note

magicpin's challenge zip contains two documents that describe submission
slightly differently:

- `challenge-brief.md` §7 shows an ~80-line reference skeleton saved as
  `bot.py`.
- `challenge-testing-brief.md` (the detailed, binding spec) confirms this
  is the **same FastAPI app** — just run via `uvicorn bot:app` instead of
  `uvicorn main:app` — deployed to a public URL, which the judge harness
  calls over HTTP.

This submission implements the full HTTP contract (all 5 endpoints +
optional teardown) in `backend/main.py`, with `backend/bot.py` provided as
a one-line re-export so `uvicorn bot:app` works identically, for maximum
compatibility with either document's exact wording. `generate_submission.py`
additionally produces a `submission.jsonl` (per `challenge-brief.md` §7.2)
by driving the real deployed bot through the 30 canonical test pairs, in
case that artifact is also collected.


## Project structure

```
nexora-bot/
├── backend/
│   ├── main.py                 # FastAPI app, lifespan, middleware, exception handlers
│   ├── bot.py                  # alias: `uvicorn bot:app` == `uvicorn main:app`
│   ├── config.py                # env-driven configuration
│   ├── dependencies.py          # FastAPI DI providers + optional auth
│   ├── middleware.py             # rate limiting + request logging
│   ├── logging_config.py         # structured JSON/dev logging
│   ├── models/                   # Pydantic schemas (context.py, requests.py, conversation.py)
│   ├── storage/                  # redis_store.py, mongo_store.py
│   ├── composer/                 # engine.py, prompt_builder.py, llm_client.py, output_validator.py, context_assembler.py
│   ├── reply/                    # handler.py, auto_reply_detector.py, intent_router.py, language_detector.py
│   ├── routers/                  # healthz, metadata, context, tick, reply, teardown, dashboard
│   ├── dataset/loader.py         # startup dataset preload
│   ├── dev_tools/                 # LOCAL-ONLY test doubles, never used in production
│   ├── tests/                     # 83 tests (unit + integration + regression)
│   ├── requirements.txt
│   ├── Dockerfile
│   └── .env.example
├── frontend/                       # Next.js 16 dashboard (5 pages, see above)
│   ├── app/  components/  lib/
│   ├── Dockerfile
│   └── .env.example
├── dataset/                        # OFFICIAL seed files + generator (unmodified)
├── expanded/                        # generated: 50 merchants / 200 customers / 100 triggers / test_pairs.json
├── examples/                         # OFFICIAL api-call-examples.md, case-studies.md (unmodified)
├── challenge-brief.md                # OFFICIAL (unmodified)
├── challenge-testing-brief.md         # OFFICIAL (unmodified)
├── engagement-design.md               # OFFICIAL (unmodified)
├── engagement-research.md              # OFFICIAL (unmodified)
├── judge_simulator.py                   # OFFICIAL (unmodified) — run with your own LLM key for real scoring
├── generate_submission.py                # drives the real bot through the 30 test pairs → submission.jsonl
├── docker-compose.yml
└── .env.example
```


## Requirements checklist

| Requirement | Status |
|---|---|
| 5 required HTTP endpoints (healthz, metadata, context, tick, reply) | ✅ |
| Optional teardown endpoint | ✅ |
| Versioned, idempotent context ingestion | ✅ |
| Suppression/dedup via Redis | ✅ |
| Trigger-kind-specific prompt composition (all 25 real trigger kinds) | ✅ |
| Output validation (URL stripping, CTA validation, anti-repetition, taboo tracking) | ✅ |
| Multi-turn reply state machine (auto-reply, hard-stop, intent transition, language switch) | ✅ |
| Groq LLM integration with retry + fallback model | ✅ |
| MongoDB persistence + indexes | ✅ |
| Redis caching, versioning, suppression, rate limiting | ✅ |
| Structured logging | ✅ |
| Rate limiting (above judge's documented ceiling) | ✅ |
| Resilient healthz (never 500s on datastore outage) | ✅ |
| Docker + docker-compose for full stack | ✅ |
| Next.js operations dashboard (5 pages) | ✅ |
| 83 automated tests against the real official dataset | ✅ |
| README, env docs, architecture, API docs, deployment guide | ✅ |
