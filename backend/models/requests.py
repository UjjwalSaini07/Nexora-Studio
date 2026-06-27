# backend/models/requests.py
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


# ── /v1/metadata ─────────────────────────────────────────────────────────────
class MetadataResponse(BaseModel):
    team_name: str
    team_members: List[str]
    model: str
    approach: str
    contact_email: str
    version: str
    submitted_at: str


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


class ContextAckResponse(BaseModel):
    accepted: bool
    ack_id: Optional[str] = None
    stored_at: Optional[str] = None
    reason: Optional[str] = None
    details: Optional[str] = None
    current_version: Optional[int] = None


# ── /v1/tick ──────────────────────────────────────────────────────────────────
class TickBody(BaseModel):
    now: str
    available_triggers: List[str] = []


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


class TickResponse(BaseModel):
    actions: List[TickAction] = []


# ── /v1/reply ──────────────────────────────────────────────────────────────────
class ReplyBody(BaseModel):
    conversation_id: str
    merchant_id: Optional[str] = None
    customer_id: Optional[str] = None
    from_role: str
    message: str
    received_at: str
    turn_number: int = Field(ge=1)

    @field_validator("message")
    @classmethod
    def message_not_blank(cls, v: str) -> str:
        if v is None:
            raise ValueError("message must not be None")
        return v


class ReplyResponse(BaseModel):
    action: Literal["send", "wait", "end"]
    body: Optional[str] = None
    cta: Optional[str] = None
    rationale: str
    wait_seconds: Optional[int] = None
