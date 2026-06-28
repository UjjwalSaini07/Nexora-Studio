from fastapi import APIRouter

from config import TEAM_NAME, TEAM_MEMBERS, CONTACT_EMAIL, BOT_VERSION, SUBMITTED_AT, LLM_MODEL, LLM_FALLBACK_MODEL
from models.requests import MetadataResponse

router = APIRouter()


@router.get("/v1/metadata", response_model=MetadataResponse)
async def metadata():
    return MetadataResponse(
        team_name=TEAM_NAME,
        team_members=TEAM_MEMBERS,
        model=LLM_MODEL,
        approach=(
            "4-context composition engine: trigger-kind dispatch -> specialized prompt "
            "variants -> Groq-hosted Llama (temperature=0) -> output validation + "
            "anti-repetition + suppression dedup. Multi-turn replies handled by a "
            "dedicated state machine (auto-reply detection, hard-stop handling, "
            "intent-transition to execution mode, language-switch tracking)."
        ),
        contact_email=CONTACT_EMAIL,
        version=BOT_VERSION,
        submitted_at=SUBMITTED_AT,
        author_portfolio="https://ujjwalsaini.vercel.app",
        author_github="https://github.com/UjjwalSaini07",
        project_description="NEXORA: A production-grade merchant engagement engine designed for the magicpin AI Challenge. Automatically translates raw business database signals (categories, merchants, customers, triggers) into hyper-personalized, context-grounded, multi-turn conversational actions.",
        llm_fallback_model=LLM_FALLBACK_MODEL,
        sla_time_budget="30s SLA (with a 22s LLM hard timeout)",
        hot_cache_type="Redis hot cache (supressions, wait-states, turn counters)",
        durable_store_type="MongoDB (context registry, action audit logs, reply history)",
        production_link="https://nexora-studio-0aaz.onrender.com/",
        frontend_dashboard_link="https://nexorabot-ai.vercel.app/",
    )
