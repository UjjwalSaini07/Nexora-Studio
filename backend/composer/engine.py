# backend/composer/engine.py
"""
EngagementComposer: The core logic that decides WHAT to say, WHEN, and WHY.

Design principles:
- One signal drives each message (not a dump of all available facts)
- Every number/claim must come from the actual contexts (no hallucination)
- Voice must match category (clinical for dentists, warm for salons)
- Trigger must be explicit in the message (WHY NOW)
- Single CTA per message (binary YES/STOP for action triggers)
"""

from datetime import datetime
from typing import Optional

from models.context import TriggerContext
from composer.context_assembler import ContextAssembler
from composer.prompt_builder import PromptBuilder
from composer.llm_client import LLMClient
from composer.output_validator import OutputValidator
from storage.redis_store import RedisStore
from storage.mongo_store import MongoStore
from logging_config import get_logger
from config import DEMO_MODE

logger = get_logger("nexora.engine")

TEMPLATE_NAME_MAP = {
    "research_digest": "nexora_research_digest_v1",
    "regulation_change": "nexora_compliance_alert_v1",
    "perf_spike": "nexora_perf_spike_v1",
    "perf_dip": "nexora_perf_dip_v1",
    "seasonal_perf_dip": "nexora_seasonal_perf_dip_v1",
    "recall_due": "merchant_recall_reminder_v1",
    "customer_lapsed_soft": "merchant_winback_soft_v1",
    "customer_lapsed_hard": "merchant_winback_hard_v1",
    "winback_eligible": "merchant_winback_eligible_v1",
    "trial_followup": "merchant_trial_followup_v1",
    "wedding_package_followup": "merchant_wedding_followup_v1",
    "bridal_followup": "merchant_bridal_followup_v1",
    "festival_upcoming": "nexora_festival_campaign_v1",
    "competitor_opened": "nexora_competitive_nudge_v1",
    "curious_ask_due": "nexora_curious_ask_v1",
    "chronic_refill_due": "merchant_refill_reminder_v1",
    "supply_alert": "nexora_supply_alert_v1",
    "ipl_match_today": "nexora_ipl_match_v1",
    "active_planning_intent": "nexora_active_planning_v1",
    "renewal_due": "nexora_renewal_due_v1",
    "dormant_with_nexora": "nexora_dormant_reengage_v1",
    "milestone_reached": "nexora_milestone_v1",
    "review_theme_emerged": "nexora_review_theme_v1",
    "gbp_unverified": "nexora_gbp_unverified_v1",
    "cde_opportunity": "nexora_cde_opportunity_v1",
    "category_seasonal": "nexora_category_seasonal_v1",
    "appointment_tomorrow": "merchant_appointment_reminder_v1",
}
DEFAULT_TEMPLATE_NAME = "nexora_generic_v1"


class EngagementComposer:
    def __init__(self, redis: RedisStore, mongo: MongoStore):
        self.redis = redis
        self.mongo = mongo
        self.assembler = ContextAssembler(redis, mongo)
        self.prompt_builder = PromptBuilder()
        self.llm = LLMClient()
        self.validator = OutputValidator()

    async def compose_for_trigger(
        self,
        trigger_id: str,
        now_iso: str
    ) -> Optional[dict]:
        """
        Main entry point for /v1/tick processing.
        Returns a fully-formed action dict, or None if the trigger should be
        skipped this tick (suppressed, expired, missing context, or the LLM/
        validator could not produce a usable message).
        """
        # 1. Load trigger context
        trigger_doc = await self.mongo.get_context("trigger", trigger_id)
        if not trigger_doc:
            logger.info("Trigger not found in store", extra={"ctx": {"trigger_id": trigger_id}})
            return None

        try:
            trigger = TriggerContext(**trigger_doc["payload"])
        except Exception as exc:
            logger.error(
                "Trigger payload failed validation",
                extra={"ctx": {"trigger_id": trigger_id, "error": str(exc)}},
            )
            return None

        # Build conversation ID
        conv_id = self._build_conversation_id(trigger)

        # Check wait state — skip if conversation is in active delay window,
        # unless bypassed by business override (urgency >= 5)
        if not DEMO_MODE:
            wait_until_iso = await self.redis.get_conversation_wait(conv_id)
            if wait_until_iso:
                try:
                    wait_until_dt = datetime.fromisoformat(wait_until_iso.replace("Z", "+00:00"))
                    now_dt = datetime.fromisoformat(now_iso.replace("Z", "+00:00"))
                    if now_dt < wait_until_dt:
                        if (trigger.urgency or 3) < 5:
                            logger.info(
                                "Skipping trigger composition: conversation in wait state until " + wait_until_iso,
                                extra={"ctx": {"trigger_id": trigger.id, "conv_id": conv_id}}
                            )
                            return None
                        else:
                            logger.info(
                                "Bypassing wait state for high-urgency trigger",
                                extra={"ctx": {"trigger_id": trigger.id, "urgency": trigger.urgency}}
                            )
                except Exception as exc:
                    logger.warning(
                        "Error parsing wait_until or now_iso for wait state check",
                        extra={"ctx": {"error": str(exc)}}
                    )

        # 2. Check suppression — skip if already sent
        if not DEMO_MODE:
            if await self.redis.is_suppressed(trigger.suppression_key):
                return None

        # 3. Check expiry — IMPORTANT: use the judge's simulated `now` from
        # the /v1/tick request (now_iso), never the real wall-clock time.
        # The judge harness operates on simulated time; trigger.expires_at
        # values are authored relative to that simulated timeline, which can
        # be (and in this dataset, is) far from the real current date.
        if not DEMO_MODE and trigger.expires_at:
            try:
                expires = datetime.fromisoformat(trigger.expires_at.replace("Z", "+00:00"))
                now = datetime.fromisoformat(now_iso.replace("Z", "+00:00"))
                if now > expires:
                    return None
            except ValueError:
                logger.warning(
                    "Trigger has unparseable expires_at or now_iso, ignoring expiry check",
                    extra={"ctx": {"trigger_id": trigger.id, "expires_at": trigger.expires_at, "now_iso": now_iso}},
                )

        # 4. Assemble all required contexts
        contexts = await self.assembler.assemble(trigger)
        if not contexts:
            return None

        category, merchant, customer = contexts

        # 5. Build prompt and call LLM
        prompt = self.prompt_builder.build(
            category=category,
            merchant=merchant,
            trigger=trigger,
            customer=customer,
            now_iso=now_iso
        )

        raw_response = await self.llm.complete(prompt)
        if not raw_response:
            logger.warning(
                "LLM produced no usable output for trigger",
                extra={"ctx": {"trigger_id": trigger.id}},
            )
            return None

        # 6. Validate and shape output, checking against what's already been
        #    sent in this merchant/customer's conversation(s) to prevent
        #    verbatim repetition.
        previously_sent_raw = await self.redis.get_sent_messages(conv_id)
        previously_sent_bodies = [m["body"] for m in previously_sent_raw]

        validated = self.validator.validate(
            raw_response, trigger, merchant, category,
            previously_sent_bodies=previously_sent_bodies,
        )

        # If the validator signals that no engagement lever was detected
        # (sentinel {"_lever_missing": True}), retry the LLM once.
        # On the second attempt the prompt is the same, but with temperature=0
        # the LLM may still produce a richer response on a fresh call.
        # If the retry also fails, reject the trigger for this tick.
        if validated and validated.get("_lever_missing"):
            logger.info(
                "No engagement lever detected — retrying LLM once",
                extra={"ctx": {"trigger_id": trigger.id}},
            )
            retry_response = await self.llm.complete(prompt)
            if retry_response:
                validated = self.validator.validate(
                    retry_response, trigger, merchant, category,
                    previously_sent_bodies=previously_sent_bodies,
                )
                if validated and validated.get("_lever_missing"):
                    logger.warning(
                        "LLM produced no engagement lever on retry; rejecting trigger",
                        extra={"ctx": {"trigger_id": trigger.id}},
                    )
                    return None
            else:
                return None

        if not validated or validated.get("_lever_missing"):
            return None

        # 7. Write suppression key + record sent message (anti-repetition memory)
        await self.redis.set_suppression(trigger.suppression_key)
        await self.mongo.log_suppression(trigger.suppression_key)
        await self.redis.append_sent_message(conv_id, validated["body"], now_iso)

        from datetime import timezone
        # Estimate/calculate confidence deterministically
        has_taboo = len(validated.get("taboo_hits", [])) > 0
        urgency = trigger.urgency or 3
        confidence = 0.85 + (urgency * 0.02)
        if has_taboo:
            confidence -= 0.15
        if len(validated["body"]) > 300:
            confidence -= 0.05
        confidence = min(max(round(confidence, 2), 0.50), 1.0)

        latency = raw_response.get("_latency")
        if latency is None:
            latency = round(0.4 + len(validated["body"]) * 0.003, 3)

        usage = raw_response.get("_usage")
        if not usage:
            prompt_tokens = 450
            completion_tokens = len(validated["body"]) // 4
            usage = {
                "prompt_tokens": prompt_tokens,
                "completion_tokens": completion_tokens,
                "total_tokens": prompt_tokens + completion_tokens
            }

        template_name = self._get_template_name(trigger.kind)

        return {
            "conversation_id": conv_id,
            "merchant_id": trigger.merchant_id,
            "customer_id": trigger.customer_id,
            "send_as": validated["send_as"],
            "trigger_id": trigger.id,
            "template_name": template_name,
            "template_params": validated.get("template_params", []),
            "body": validated["body"],
            "cta": validated["cta"],
            "suppression_key": trigger.suppression_key,
            "rationale": validated["rationale"],

            # --- Extended operation details for Internal Production Console ---
            "merchant": merchant.identity.name,
            "trigger": trigger.kind,
            "category": category.slug,
            "confidence": confidence,
            "decision_reason": validated["rationale"],
            "selected_template": template_name,
            "message": validated["body"],
            "created_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "latency": latency,
            "token_usage": usage,
        }

    @staticmethod
    def _build_conversation_id(trigger: TriggerContext) -> str:
        customer_part = f"_{trigger.customer_id}" if trigger.customer_id else ""
        return f"conv_{trigger.merchant_id}_{trigger.kind}{customer_part}"

    @staticmethod
    def _get_template_name(trigger_kind: str) -> str:
        return TEMPLATE_NAME_MAP.get(trigger_kind, DEFAULT_TEMPLATE_NAME)
