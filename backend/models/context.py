# backend/models/context.py
"""
Core domain models for the 4 context types VERA receives:
CategoryContext, MerchantContext, CustomerContext, TriggerContext.

These are intentionally PERMISSIVE rather than strict. The real challenge
dataset (magicpin-ai-challenge.zip) has meaningfully heterogeneous shapes
across records of the same scope:
  - `subscription` sometimes has `days_remaining`, sometimes
    `days_since_expiry` (depends on status: active/trial vs expired).
  - `customer_aggregate` varies its fields per category (a dentist's
    aggregate has `high_risk_adult_count`; a gym's has `active_members`;
    some have neither `lapsed_180d_plus` nor `retention_6mo_pct`).
  - Per-record extra fields appear ad hoc (`review_themes`, "dine_in_orders_30d",
    etc.) that aren't part of the documented schema but are clearly meant to
    flow through to the composer as extra signal.
  - `digest` items vary fields by `kind` (research/compliance/trend/cde/tech).
  - `offers[].started`/`ended` are date-only strings, not always present.

Design choice: every field that is "almost always present" is still declared
(so prompt_builder.py gets typed, autocompleted access), but is Optional with
a safe default. Every sub-model uses `extra="allow"` so unexpected fields
from the real dataset are preserved rather than silently dropped or causing
a 422 on /v1/context. This trades strict validation for resilience, which
matches the judge harness's actual behavior: it pushes whatever shape a
given record has, and a bot that 422s on real merchant #4 is disqualified
for that test slot.
"""
import warnings

from pydantic import BaseModel, Field, ConfigDict
from typing import Optional, List, Dict, Any

# "register" is a normal business field name on VoiceProfile; Pydantic warns
# because it shadows a now-unused internal attribute name on BaseModel in
# some versions. This has no functional effect on validation/serialization,
# so we suppress just this specific warning rather than disabling all
# Pydantic warnings module-wide. Matched by regex since the parent class name
# in the message can vary (BaseModel vs an intermediate base like _Permissive).
warnings.filterwarnings(
    "ignore",
    message=r'Field name "register" in ".*" shadows an attribute in parent ".*"',
    category=UserWarning,
)


class _Permissive(BaseModel):
    """Base class: tolerate unexpected extra fields instead of rejecting them."""
    model_config = ConfigDict(extra="allow")


# ── CategoryContext ───────────────────────────────────────────────
class VoiceProfile(_Permissive):
    tone: str = "neutral"
    register: Optional[str] = None
    code_mix: Optional[str] = None
    vocab_allowed: List[str] = []
    vocab_taboo: List[str] = []
    salutation_examples: List[str] = []
    tone_examples: List[str] = []


class OfferTemplate(_Permissive):
    id: Optional[str] = None
    title: str
    value: Optional[str] = None
    audience: Optional[str] = None
    type: Optional[str] = None


class PeerStats(_Permissive):
    scope: Optional[str] = None
    avg_rating: Optional[float] = None
    avg_reviews: Optional[float] = None
    avg_review_count: Optional[float] = None
    avg_ctr: Optional[float] = None
    avg_views_30d: Optional[float] = None
    avg_calls_30d: Optional[float] = None
    avg_directions_30d: Optional[float] = None
    avg_photos: Optional[float] = None
    avg_post_freq_days: Optional[float] = None
    retention_6mo_pct: Optional[float] = None

    @property
    def reviews(self) -> Optional[float]:
        """Unified accessor — the dataset spells this two different ways."""
        return self.avg_reviews if self.avg_reviews is not None else self.avg_review_count


class DigestItem(_Permissive):
    id: str
    kind: str          # "research", "compliance", "trend", "news", "cde", "tech"
    title: str
    source: Optional[str] = None
    summary: Optional[str] = None
    trial_n: Optional[int] = None
    patient_segment: Optional[str] = None
    actionable: Optional[str] = None
    date: Optional[str] = None
    credits: Optional[float] = None


class ContentItem(_Permissive):
    id: str
    title: str
    channel: Optional[str] = None
    body: Optional[str] = None
    length_seconds: Optional[int] = None


class SeasonalBeat(_Permissive):
    month_range: str
    note: str


class TrendSignal(_Permissive):
    query: str
    delta_yoy: Optional[float] = None
    segment_age: Optional[str] = None
    skew: Optional[str] = None


class CategoryContext(_Permissive):
    slug: str
    display_name: Optional[str] = None
    voice: VoiceProfile = VoiceProfile()
    offer_catalog: List[OfferTemplate] = []
    peer_stats: PeerStats = PeerStats()
    digest: List[DigestItem] = []
    patient_content_library: List[ContentItem] = []
    seasonal_beats: List[SeasonalBeat] = []
    trend_signals: List[TrendSignal] = []
    regulatory_authorities: List[str] = []
    professional_journals: List[str] = []


# ── MerchantContext ───────────────────────────────────────────────
class Identity(_Permissive):
    name: str
    city: Optional[str] = None
    locality: Optional[str] = None
    place_id: Optional[str] = None
    verified: bool = False
    languages: List[str] = ["en"]
    owner_first_name: Optional[str] = None
    established_year: Optional[int] = None


class Subscription(_Permissive):
    status: str = "active"
    plan: Optional[str] = None
    days_remaining: Optional[int] = None
    days_since_expiry: Optional[int] = None
    renewed_at: Optional[str] = None


class DeltaPerf(_Permissive):
    views_pct: Optional[float] = None
    calls_pct: Optional[float] = None
    ctr_pct: Optional[float] = None


class PerformanceSnapshot(_Permissive):
    window_days: int = 30
    views: Optional[int] = None
    calls: Optional[int] = None
    directions: Optional[int] = None
    ctr: Optional[float] = None
    leads: Optional[int] = None
    delta_7d: Optional[DeltaPerf] = None


class MerchantOffer(_Permissive):
    id: Optional[str] = None
    title: str
    status: str = "active"          # "active", "paused", "expired"
    started: Optional[str] = None
    ended: Optional[str] = None


class ConversationTurn(_Permissive):
    model_config = ConfigDict(populate_by_name=True, extra="allow")

    ts: Optional[str] = None
    from_: str = Field(alias="from")
    body: str
    engagement: Optional[str] = None  # "merchant_replied", "ignored", "auto_reply", "intent_action"


class CustomerAggregate(_Permissive):
    """
    Deliberately has NO required fields: real category data populates a
    different subset per vertical (dentists -> high_risk_adult_count, gyms ->
    active_members, restaurants -> dine_in_orders_30d, etc. — and some of
    those exact key names aren't known ahead of time). `extra="allow"`
    ensures any category-specific aggregate field still reaches the prompt
    builder via `.model_extra`.
    """
    total_unique_ytd: Optional[int] = None
    lapsed_180d_plus: Optional[int] = None
    retention_6mo_pct: Optional[float] = None
    retention_3mo_pct: Optional[float] = None
    high_risk_adult_count: Optional[int] = None
    active_members: Optional[int] = None


class ReviewTheme(_Permissive):
    theme: str
    sentiment: Optional[str] = None
    occurrences_30d: Optional[int] = None
    common_quote: Optional[str] = None


class MerchantContext(_Permissive):
    merchant_id: str
    category_slug: str
    identity: Identity
    subscription: Subscription = Subscription()
    performance: PerformanceSnapshot = PerformanceSnapshot()
    offers: List[MerchantOffer] = []
    conversation_history: List[ConversationTurn] = []
    customer_aggregate: Optional[CustomerAggregate] = None
    signals: List[str] = []
    review_themes: List[ReviewTheme] = []


# ── CustomerContext ───────────────────────────────────────────────
class CustomerIdentity(_Permissive):
    name: str
    phone_redacted: Optional[str] = None
    language_pref: str = "en"
    age_band: Optional[str] = None


class Relationship(_Permissive):
    first_visit: Optional[str] = None
    last_visit: Optional[str] = None
    visits_total: int = 0
    services_received: List[str] = []
    lifetime_value: Optional[float] = None


class Preferences(_Permissive):
    preferred_slots: Optional[str] = None
    channel: str = "whatsapp"
    reminder_opt_in: bool = True


class Consent(_Permissive):
    opted_in_at: Optional[str] = None
    scope: List[str] = []


class CustomerContext(_Permissive):
    customer_id: str
    merchant_id: str
    identity: CustomerIdentity
    relationship: Relationship = Relationship()
    state: str = "active"  # "new", "active", "lapsed_soft", "lapsed_hard", "churned"
    preferences: Preferences = Preferences()
    consent: Consent = Consent()


# ── TriggerContext ────────────────────────────────────────────────
class TriggerContext(_Permissive):
    id: str
    scope: str          # "merchant" or "customer"
    kind: str           # "research_digest", "recall_due", "perf_spike", ... (24+ kinds)
    source: str         # "external" or "internal"
    merchant_id: Optional[str] = None
    customer_id: Optional[str] = None
    payload: Dict[str, Any] = {}
    urgency: int = 3    # 1-5
    suppression_key: str
    expires_at: Optional[str] = None


# ── Stored context wrapper ────────────────────────────────────────
class StoredContext(_Permissive):
    scope: str
    context_id: str
    version: int
    payload: Dict[str, Any]
    delivered_at: str
    stored_at: str
