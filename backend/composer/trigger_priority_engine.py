"""
TriggerPriorityEngine: Ranks available triggers before any LLM call.

Priority score (0-100) is computed deterministically from:
  urgency          (0-25 pts) — direct from trigger.urgency (1-5 scale)
  expiry_proximity (0-25 pts) — triggers expiring sooner rank higher
  kind_weight      (0-20 pts) — business-critical kinds rank higher
  source_weight    (0-10 pts) — external > internal for immediacy
  scope_weight     (0-10 pts) — customer-scoped (revenue) > merchant
  payload_richness (0-10 pts) — triggers with richer payloads rank higher

Design notes:
- Fully synchronous (no I/O) so it can be called before the async gather.
- Returns a ranked list of (trigger_id, score, reason) tuples.
- Ties broken by trigger_id lexicographic order for full determinism.
- Never raises — missing or malformed data scores 0 for that dimension.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import List, Tuple

from logging_config import get_logger

logger = get_logger("nexora.priority_engine")

# ── Kind weights: higher = more immediate business impact ──────────────────────
# Based on the official engagement-design.md urgency guidance.
_KIND_WEIGHTS: dict[str, int] = {
    # Critical / time-bound
    "supply_alert":              20,
    "regulation_change":         20,
    "appointment_tomorrow":      18,
    "recall_due":                18,
    "chronic_refill_due":        18,
    # High commercial value
    "renewal_due":               16,
    "perf_spike":                15,
    "perf_dip":                  14,
    "seasonal_perf_dip":         14,
    "competitor_opened":         14,
    # Customer lifecycle
    "customer_lapsed_hard":      13,
    "winback_eligible":          12,
    "bridal_followup":           12,
    "wedding_package_followup":  12,
    "trial_followup":            11,
    "customer_lapsed_soft":      10,
    # Category/event driven
    "ipl_match_today":           13,
    "festival_upcoming":         12,
    "category_seasonal":         10,
    # Informational / relationship
    "milestone_reached":          9,
    "review_theme_emerged":        9,
    "gbp_unverified":              9,
    "cde_opportunity":             9,
    "research_digest":             8,
    "active_planning_intent":      8,
    "dormant_with_nexora":          6,
    "curious_ask_due":             5,
}
_DEFAULT_KIND_WEIGHT = 7

# Maximum hours-until-expiry to get the full 25 pts; beyond this, the
# expiry-proximity score tapers to 0.
_EXPIRY_FULL_SCORE_HOURS = 24.0
_EXPIRY_ZERO_SCORE_HOURS = 168.0  # 7 days


def _score_urgency(urgency: int) -> Tuple[int, str]:
    """Maps urgency 1-5 → 5-25 points."""
    clamped = max(1, min(5, int(urgency)))
    pts = clamped * 5
    return pts, f"urgency={clamped}/5 → {pts}pts"


def _score_expiry(expires_at: str | None, now: datetime) -> Tuple[int, str]:
    """Triggers expiring sooner get higher scores."""
    if not expires_at:
        return 12, "no expiry → neutral 12pts"
    try:
        expires = datetime.fromisoformat(expires_at.replace("Z", "+00:00"))
        hours_left = (expires - now).total_seconds() / 3600
        if hours_left < 0:
            return 0, f"expired {abs(hours_left):.1f}h ago → 0pts"
        if hours_left <= _EXPIRY_FULL_SCORE_HOURS:
            pts = 25
        elif hours_left >= _EXPIRY_ZERO_SCORE_HOURS:
            pts = 0
        else:
            ratio = 1 - (hours_left - _EXPIRY_FULL_SCORE_HOURS) / (_EXPIRY_ZERO_SCORE_HOURS - _EXPIRY_FULL_SCORE_HOURS)
            pts = int(ratio * 25)
        return pts, f"expires_in={hours_left:.1f}h → {pts}pts"
    except (ValueError, OverflowError):
        return 12, "unparseable expiry → neutral 12pts"


def _score_kind(kind: str) -> Tuple[int, str]:
    pts = _KIND_WEIGHTS.get(kind, _DEFAULT_KIND_WEIGHT)
    return pts, f"kind={kind} → {pts}pts"


def _score_source(source: str) -> Tuple[int, str]:
    if source == "external":
        return 10, "source=external → 10pts"
    return 6, "source=internal → 6pts"


def _score_scope(scope: str) -> Tuple[int, str]:
    if scope == "customer":
        return 10, "scope=customer (direct revenue) → 10pts"
    return 7, "scope=merchant → 7pts"


def _score_payload_richness(payload: dict) -> Tuple[int, str]:
    """More payload keys = richer context = slightly higher priority."""
    count = len(payload)
    if count >= 5:
        return 10, f"payload_keys={count} → 10pts"
    pts = max(0, count * 2)
    return pts, f"payload_keys={count} → {pts}pts"


def rank_triggers(
    trigger_docs: list[dict],
    now_iso: str,
) -> list[dict]:
    """
    Given a list of raw trigger payload dicts (already loaded from MongoDB),
    return them sorted by descending priority score.

    Each returned dict is the original trigger_doc augmented with:
      _priority_score  (int, 0-100)
      _priority_reason (str, human-readable breakdown)
      _priority_rank   (int, 1-based)

    Triggers whose doc is None/missing are filtered out silently.
    """
    try:
        now = datetime.fromisoformat(now_iso.replace("Z", "+00:00"))
    except (ValueError, AttributeError):
        now = datetime.now(timezone.utc)
        logger.warning("Invalid now_iso for priority ranking, using wall clock",
                       extra={"ctx": {"now_iso": now_iso}})

    scored: list[tuple[int, str, str, dict]] = []  # (score, reason, trigger_id, doc)

    for doc in trigger_docs:
        if not doc:
            continue
        payload = doc.get("payload", {})
        trigger_id = doc.get("context_id", payload.get("id", "unknown"))

        urgency      = payload.get("urgency", 3)
        expires_at   = payload.get("expires_at")
        kind         = payload.get("kind", "")
        source       = payload.get("source", "internal")
        scope        = payload.get("scope", "merchant")

        u_pts, u_reason    = _score_urgency(urgency)
        e_pts, e_reason    = _score_expiry(expires_at, now)
        k_pts, k_reason    = _score_kind(kind)
        s_pts, s_reason    = _score_source(source)
        sc_pts, sc_reason  = _score_scope(scope)
        p_pts, p_reason    = _score_payload_richness(payload)

        total = u_pts + e_pts + k_pts + s_pts + sc_pts + p_pts
        total = min(100, total)

        reason = (
            f"score={total}: "
            f"[{u_reason}] + [{e_reason}] + [{k_reason}] + "
            f"[{s_reason}] + [{sc_reason}] + [{p_reason}]"
        )

        scored.append((total, trigger_id, reason, doc))

    # Sort: highest score first; ties broken by trigger_id (lexicographic) for determinism
    scored.sort(key=lambda x: (-x[0], x[1]))

    result = []
    for rank, (score, trigger_id, reason, doc) in enumerate(scored, start=1):
        enriched = dict(doc)
        enriched["_priority_score"] = score
        enriched["_priority_reason"] = reason
        enriched["_priority_rank"] = rank
        result.append(enriched)

        logger.debug(
            "Trigger ranked",
            extra={"ctx": {"rank": rank, "trigger_id": trigger_id, "score": score}},
        )

    return result
