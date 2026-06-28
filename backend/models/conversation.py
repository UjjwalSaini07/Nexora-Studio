"""
Typed representations of a conversation's turn-by-turn state.

RedisStore persists conversations as plain JSON lists of dicts (cheap, fast,
TTL-friendly). These Pydantic models give the rest of the codebase
(ReplyHandler, dashboard API, tests) a typed view over that same data so we
don't pass raw dicts around once we're inside business logic.
"""
from datetime import datetime
from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, Field


class TurnRole(str, Enum):
    MERCHANT = "merchant"
    CUSTOMER = "customer"
    NEXORA = "nexora"
    SYSTEM = "system"


class ReplyAction(str, Enum):
    SEND = "send"
    WAIT = "wait"
    END = "end"


class Turn(BaseModel):
    """A single message in a conversation, in either direction."""
    from_: str = Field(alias="from")
    message: str
    received_at: Optional[str] = None
    sent_at: Optional[str] = None
    turn_number: int
    is_auto_reply: bool = False

    class Config:
        populate_by_name = True


class ConversationState(BaseModel):
    """
    Aggregate, derived view of a conversation — built on demand from the
    raw turn list stored in Redis (`nexora:conv:{conv_id}`), not stored
    directly itself. Useful for the dashboard and for reasoning about
    state transitions in tests.
    """
    conversation_id: str
    merchant_id: Optional[str] = None
    customer_id: Optional[str] = None
    turns: List[Turn] = []
    ended: bool = False
    auto_reply_streak: int = 0
    last_action: Optional[ReplyAction] = None

    @property
    def turn_count(self) -> int:
        return len(self.turns)

    @property
    def last_turn(self) -> Optional[Turn]:
        return self.turns[-1] if self.turns else None

    @classmethod
    def from_raw(
        cls,
        conversation_id: str,
        raw_turns: list[dict],
        ended: bool = False,
        auto_reply_streak: int = 0,
        merchant_id: Optional[str] = None,
        customer_id: Optional[str] = None,
    ) -> "ConversationState":
        turns = [Turn(**t) for t in raw_turns]
        return cls(
            conversation_id=conversation_id,
            merchant_id=merchant_id,
            customer_id=customer_id,
            turns=turns,
            ended=ended,
            auto_reply_streak=auto_reply_streak,
        )
