# backend/routers/metadata.py
from fastapi import APIRouter

from config import TEAM_NAME, TEAM_MEMBERS, CONTACT_EMAIL, BOT_VERSION, SUBMITTED_AT, LLM_MODEL
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
    )
