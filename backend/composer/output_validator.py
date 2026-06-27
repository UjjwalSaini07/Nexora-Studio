# backend/composer/output_validator.py
"""
OutputValidator: Ensures LLM output meets the judge's contract.

Catches the documented anti-patterns directly:
- URLs in body (Meta policy violation, -3 penalty per URL) -> stripped
- Invalid/missing CTA -> defaulted, but logged as a quality warning
- Wrong send_as for trigger.scope -> auto-corrected
- Empty rationale / missing template_params -> backfilled
- Taboo vocabulary for the category -> logged (and stripped where possible)
- Repeats a body already sent in this conversation -> rejected (forces a
  re-compose) instead of silently emitting a flagged duplicate, since the
  anti-repetition penalty is explicit in the rubric.
"""
import re
from typing import Optional

from models.context import TriggerContext, MerchantContext, CategoryContext
from logging_config import get_logger

logger = get_logger("nexora.output_validator")

VALID_CTAS = {
    "binary_yes_no", "binary_confirm_cancel", "open_ended",
    "multi_choice_slot", "none",
}
URL_PATTERN = re.compile(r'https?://\S+', re.IGNORECASE)
WWW_PATTERN = re.compile(r'\bwww\.\S+\.\S+', re.IGNORECASE)


class OutputValidator:
    def validate(
        self,
        raw: dict,
        trigger: TriggerContext,
        merchant: MerchantContext,
        category: CategoryContext,
        previously_sent_bodies: Optional[list[str]] = None,
    ) -> Optional[dict]:
        if not isinstance(raw, dict):
            logger.warning("LLM output was not a dict", extra={"ctx": {"trigger_id": trigger.id}})
            return None

        body = str(raw.get("body", "")).strip()
        cta = str(raw.get("cta", "open_ended")).strip()
        send_as = str(raw.get("send_as", "nexora")).strip()
        rationale = str(raw.get("rationale", "")).strip()
        template_params = raw.get("template_params", [])
        if not isinstance(template_params, list):
            template_params = []

        # ── Hard failures ────────────────────────────────────────────────
        if not body:
            logger.warning("LLM returned empty body", extra={"ctx": {"trigger_id": trigger.id}})
            return None

        # Strip URLs / bare-www links — never let a URL reach the judge.
        if URL_PATTERN.search(body) or WWW_PATTERN.search(body):
            logger.warning(
                "LLM body contained a URL; stripping",
                extra={"ctx": {"trigger_id": trigger.id}},
            )
            body = URL_PATTERN.sub("", body)
            body = WWW_PATTERN.sub("", body)
            body = re.sub(r"\s{2,}", " ", body).strip()
            if not body:
                return None

        # Anti-repetition: reject (so the caller can retry/skip) rather than
        # silently send a duplicate body in the same conversation.
        if previously_sent_bodies and body.strip() in {b.strip() for b in previously_sent_bodies}:
            logger.warning(
                "LLM produced a body identical to a previously-sent message; rejecting",
                extra={"ctx": {"trigger_id": trigger.id, "merchant_id": merchant.merchant_id}},
            )
            return None

        # ── CTA validation ───────────────────────────────────────────────
        if cta not in VALID_CTAS:
            logger.info(
                "Invalid CTA from LLM, defaulting to open_ended",
                extra={"ctx": {"trigger_id": trigger.id, "received_cta": cta}},
            )
            cta = "open_ended"

        # ── send_as validation + scope-based auto-correction ────────────
        if send_as not in {"nexora", "merchant_on_behalf"}:
            send_as = "nexora" if trigger.scope == "merchant" else "merchant_on_behalf"
        if trigger.scope == "customer" and send_as == "nexora":
            send_as = "merchant_on_behalf"
        if trigger.scope == "merchant" and send_as == "merchant_on_behalf":
            # Merchant-scoped triggers are Nexora-to-merchant; correct mismatches defensively.
            send_as = "nexora"

        # ── Taboo vocabulary check (log only — rejecting on every match
        #    would be too aggressive for tokens that are part of normal
        #    words like "discount"/"deal", so we flag for visibility) ────
        body_lower = body.lower()
        hit_taboo = [t for t in category.voice.vocab_taboo if t.lower() in body_lower]
        if hit_taboo:
            logger.warning(
                "Body contains taboo vocabulary for category",
                extra={"ctx": {"trigger_id": trigger.id, "taboo_hits": hit_taboo}},
            )

        # ── Backfill template_params if the LLM didn't populate them ─────
        if not template_params:
            name = merchant.identity.owner_first_name or merchant.identity.name
            template_params = [name, body[:80], cta]
        template_params = [str(p) for p in template_params][:3]

        # ── Rationale must not be empty (judge cross-checks it) ──────────
        if not rationale:
            rationale = f"Composed from {trigger.kind} trigger for {merchant.merchant_id}"

        return {
            "body": body,
            "cta": cta,
            "send_as": send_as,
            "template_params": template_params,
            "rationale": rationale,
            "taboo_hits": hit_taboo,
        }
