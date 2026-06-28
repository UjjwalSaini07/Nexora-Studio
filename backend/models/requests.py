"""
Request/response schemas for the 5 judge-facing endpoints.

Router modules import these rather than declaring inline BaseModels, so the
wire contract lives in exactly one place and stays consistent across
context.py, tick.py, reply.py, healthz.py, and metadata.py.
"""
from pydantic import BaseModel, Field, field_validator
from typing import Any, List, Optional, Literal


# ── /v1/healthz ──────────────────────────────────────────────────────────────
class HealthzResponse(BaseModel):
    status: Literal["ok", "degraded", "down"]
    uptime_seconds: int
    contexts_loaded: dict[str, int]
    mongo_connected: bool = True
    redis_connected: bool = True
    total_actions_logged: Optional[int] = None
    total_replies_logged: Optional[int] = None
    active_suppression_keys: Optional[int] = None
    system_start_time: Optional[str] = None
    environment: Optional[str] = None
    memory_usage_mb: Optional[float] = None


# ── /v1/metadata ─────────────────────────────────────────────────────────────
class MetadataResponse(BaseModel):
    team_name: str
    team_members: List[str]
    model: str
    approach: str
    contact_email: str
    version: str
    submitted_at: str
    author_portfolio: Optional[str] = None
    author_github: Optional[str] = None
    project_description: Optional[str] = None
    llm_fallback_model: Optional[str] = None
    sla_time_budget: Optional[str] = None
    hot_cache_type: Optional[str] = None
    durable_store_type: Optional[str] = None
    production_link: Optional[str] = None
    frontend_dashboard_link: Optional[str] = None


# ── /v1/context ──────────────────────────────────────────────────────────────
VALID_SCOPES = {"category", "merchant", "customer", "trigger"}


class ContextBody(BaseModel):
    scope: str
    context_id: str
    version: int = Field(ge=0)
    payload: dict[str, Any]
    delivered_at: str

    @field_validator("context_id")
    @classmethod
    def context_id_not_blank(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("context_id must not be blank")
        return v

    @field_validator("delivered_at")
    @classmethod
    def delivered_at_valid(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("delivered_at must not be blank")
        try:
            from datetime import datetime
            datetime.fromisoformat(v.replace("Z", "+00:00"))
            return v
        except Exception:
            raise ValueError("Invalid ISO 8601 timestamp format for delivered_at")


class ContextAckResponse(BaseModel):
    accepted: bool
    ack_id: Optional[str] = None
    stored_at: Optional[str] = None
    reason: Optional[str] = None
    details: Optional[str] = None
    current_version: Optional[int] = None
    processing_ms: Optional[float] = None


# ── /v1/tick ──────────────────────────────────────────────────────────────────
class TickBody(BaseModel):
    now: str
    available_triggers: List[str] = []

    @field_validator("now")
    @classmethod
    def now_valid(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("now must not be blank")
        try:
            from datetime import datetime
            datetime.fromisoformat(v.replace("Z", "+00:00"))
            return v
        except Exception:
            raise ValueError("Invalid ISO 8601 timestamp format for now")


class TickAction(BaseModel):
    conversation_id: str
    merchant_id: Optional[str] = None
    customer_id: Optional[str] = None
    send_as: Literal["nexora", "merchant_on_behalf"]
    trigger_id: str
    template_name: str
    template_params: List[str] = []
    body: str
    cta: str
    suppression_key: str
    rationale: str
    priority_score: Optional[int] = None
    priority_rank: Optional[int] = None
    trigger_kind: Optional[str] = None
    urgency: Optional[int] = None
    expires_at: Optional[str] = None


class TickResponse(BaseModel):
    actions: List[TickAction] = []
    processing_ms: Optional[float] = None


# ── /v1/reply ──────────────────────────────────────────────────────────────────
class ReplyBody(BaseModel):
    conversation_id: str
    merchant_id: Optional[str] = None
    customer_id: Optional[str] = None
    from_role: str
    message: str
    received_at: str
    turn_number: int = Field(ge=1)

    @field_validator("conversation_id")
    @classmethod
    def conversation_id_not_blank(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("conversation_id must not be blank")
        return v

    @field_validator("message")
    @classmethod
    def message_not_blank(cls, v: str) -> str:
        if v is None:
            raise ValueError("message must not be None")
        if not v.strip():
            raise ValueError("message must not be empty or whitespace-only")
        return v

    @field_validator("received_at")
    @classmethod
    def received_at_valid(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("received_at must not be blank")
        try:
            from datetime import datetime
            datetime.fromisoformat(v.replace("Z", "+00:00"))
            return v
        except Exception:
            raise ValueError("Invalid ISO 8601 timestamp format for received_at")


class ReplyResponse(BaseModel):
    action: Literal["send", "wait", "end"]
    body: Optional[str] = None
    cta: Optional[str] = None
    rationale: str
    wait_seconds: Optional[int] = None
    processing_ms: Optional[float] = None
