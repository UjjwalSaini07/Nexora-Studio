# NEXORA Backend

FastAPI application implementing the full magicpin AI Challenge HTTP
contract. See the [repo-level README](../README.md) for architecture,
deployment, and the full requirements checklist.

## Setup

```bash
cp .env.example .env     # set GROQ_API_KEY at minimum
pip install -r requirements.txt

# Needs a reachable MongoDB and Redis. Locally:
#   redis-server --daemonize yes
#   mongod --dbpath /tmp/mongo-data &

python3 ../dataset/generate_dataset.py --seed-dir ../dataset --out ../expanded

uvicorn main:app --host 0.0.0.0 --port 8080 --reload
```

## Running tests

```bash
pip install -r requirements.txt   # includes pytest, fakeredis, mongomock-motor
pytest tests/ -v
```

No real MongoDB/Redis/Groq required to run the test suite — `fakeredis`
and `mongomock-motor` stand in for the datastores, and LLM calls are
mocked at the `LLMClient.complete` boundary so tests are deterministic
and fully offline.

## Module map

| Module | Responsibility |
|---|---|
| `main.py` | App assembly: lifespan (dataset preload, index creation), middleware, exception handlers, route registration |
| `bot.py` | One-line alias re-exporting `main.app`, so `uvicorn bot:app` works per the testing brief's reference skeleton |
| `config.py` | All environment-driven configuration in one place |
| `dependencies.py` | FastAPI `Depends()` providers for the Redis/Mongo store singletons + optional bearer-token auth |
| `middleware.py` | Redis-backed rate limiting (fails open on Redis errors) + structured request logging |
| `logging_config.py` | JSON logging in production, colored dev logging otherwise |
| `models/context.py` | Pydantic models for the 4 context types — deliberately permissive (`extra="allow"`, mostly-Optional fields) because the real dataset's field presence varies meaningfully across records of the same scope |
| `models/requests.py` | Request/response schemas for the 5 endpoints |
| `models/conversation.py` | Typed `Turn`/`ConversationState` views over the raw Redis-stored turn lists |
| `storage/redis_store.py` | Context version index, suppression keys, conversation state, auto-reply streak, rate-limit counters, teardown wipe |
| `storage/mongo_store.py` | Context persistence, actions/replies audit log, indexes, teardown wipe |
| `composer/context_assembler.py` | Resolves+validates the (category, merchant, customer?) tuple a trigger needs; returns `None` (never raises) on anything missing |
| `composer/prompt_builder.py` | The highest-leverage file: master system prompt + 27 trigger-kind-specific addenda |
| `composer/llm_client.py` | Groq (OpenAI-compatible) client: JSON mode, retries with backoff, automatic fallback model |
| `composer/output_validator.py` | Schema enforcement: URL stripping, CTA validation, send_as auto-correction, anti-repetition rejection, taboo-word tracking |
| `composer/engine.py` | `EngagementComposer` — orchestrates the whole compose-for-trigger pipeline; **uses the simulated `now` from the request, never real wall-clock time**, for expiry checks |
| `reply/handler.py` | Multi-turn state machine: auto-reply streak (send → wait → end), hard-stop handling, intent-transition surfacing, language-switch detection |
| `reply/auto_reply_detector.py` / `intent_router.py` / `language_detector.py` | Small, independently-testable heuristic detectors used by the handler |
| `routers/*.py` | One file per endpoint, thin — all real logic lives in `composer`/`reply`/`storage` |
| `dataset/loader.py` | Resolves and preloads the dataset directory at startup (`expanded/` if generated, else falls back to `dataset/` seeds) |
| `dev_tools/` | **Not used in production.** Local-only mock LLM servers and a sandbox app runner, for testing without live Mongo/Redis/Groq access |

## A note on `models/context.py`'s permissiveness

The official dataset (`magicpin-ai-challenge.zip`) is meaningfully
heterogeneous: `subscription` has either `days_remaining` or
`days_since_expiry` depending on status; `customer_aggregate` populates a
different subset of fields per category; some merchants carry extra
ad-hoc fields like `review_themes`. Pydantic models here use
`extra="allow"` and mostly-`Optional` fields so the bot never 422s on a
real record — strictness was deliberately traded for resilience, since a
context push rejected at test time costs far more than a slightly looser
schema.
