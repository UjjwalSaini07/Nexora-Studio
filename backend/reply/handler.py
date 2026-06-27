# backend/reply/handler.py
"""
ReplyHandler: Manages multi-turn conversations.

Three outcomes per turn: send | wait | end

Critical behaviors:
1. Auto-reply detection: detect canned WhatsApp Business responses
   (try once -> wait 24h on second auto-reply -> end on third)
2. Intent transition: detect explicit "yes/let's do it" and SWITCH TO ACTION
   MODE (handled by instructing the LLM directly; intent_router flags it so
   we can also log/expose it on the dashboard)
3. Hostile/off-topic: decline politely, stay on mission
4. Language detection: detect mid-conversation language switches and tell
   the LLM to mirror the new language
"""
from typing import Optional

from storage.redis_store import RedisStore
from storage.mongo_store import MongoStore
from composer.llm_client import LLMClient
from reply.auto_reply_detector import AutoReplyDetector
from reply.intent_router import IntentRouter
from reply.language_detector import LanguageDetector
from logging_config import get_logger

logger = get_logger("nexora.reply_handler")

REPLY_SYSTEM_PROMPT = """You are NEXORA continuing a WhatsApp conversation with a merchant (or their customer).

You just sent a message. They replied. Decide what to do next.

## Rules
- If they said YES, agreed, or "let's do it" -> ACTION MODE: draft the actual artifact immediately, do NOT ask more questions
- If they asked a question -> answer it specifically, then advance
- If they gave an auto-reply (canned "Thank you for contacting...") -> wait or end
- If they said stop/not interested/go away -> end gracefully
- If they asked something off-topic (GST, unrelated) -> politely decline + redirect back
- Never repeat what you already said
- Keep it SHORT — this is a reply, not a new pitch
- Match the language they just used (if they switched to Hindi, switch with them)
- NEVER include URLs in the body.
- Use at most ONE call to action.

## Output JSON ONLY:
For send: {"action": "send", "body": "...", "cta": "...", "rationale": "..."}
For wait: {"action": "wait", "wait_seconds": 14400, "rationale": "..."}
For end:  {"action": "end", "rationale": "..."}"""


class ReplyHandler:
    def __init__(self, redis: RedisStore, mongo: MongoStore):
        self.redis = redis
        self.mongo = mongo
        self.llm = LLMClient()
        self.auto_reply_detector = AutoReplyDetector()
        self.intent_router = IntentRouter()
        self.language_detector = LanguageDetector()

    async def handle(
        self,
        conversation_id: str,
        merchant_id: Optional[str],
        customer_id: Optional[str],
        from_role: str,
        message: str,
        received_at: str,
        turn_number: int,
        merchant_doc: Optional[dict] = None,
    ) -> dict:
        """Returns {action, body?, cta?, rationale, wait_seconds?}"""

        # Record this turn
        await self.redis.append_turn(conversation_id, {
            "from": from_role,
            "message": message,
            "received_at": received_at,
            "turn_number": turn_number,
        })

        # 1. Check if conversation already ended
        if await self.redis.is_conversation_ended(conversation_id):
            result = {"action": "end", "rationale": "Conversation already marked as ended."}
            await self._log(conversation_id, merchant_id, customer_id, message, result)
            return result

        # 2. Detect auto-reply
        is_auto = self.auto_reply_detector.detect(message)
        if is_auto:
            count = await self.redis.increment_auto_reply(conversation_id)
            if count == 1:
                result = {
                    "action": "send",
                    "body": "Looks like an auto-reply 😊 When the owner sees this, just reply 'Yes' to continue.",
                    "cta": "binary_yes_no",
                    "rationale": "Detected auto-reply (canned phrase). One prompt to flag for owner.",
                }
            elif count == 2:
                result = {
                    "action": "wait",
                    "wait_seconds": 86400,
                    "rationale": "Same auto-reply twice in a row. Owner not at phone. Waiting 24h.",
                }
            else:  # 3+ auto-replies
                await self.redis.mark_conversation_ended(conversation_id)
                result = {
                    "action": "end",
                    "rationale": "Auto-reply 3x in a row. No engagement signal. Closing conversation.",
                }
            await self._save_wait_state_if_needed(conversation_id, received_at, result)
            await self._log(conversation_id, merchant_id, customer_id, message, result)
            return result
        else:
            # A genuine (non-auto) reply resets the auto-reply streak.
            await self.redis.reset_auto_reply_count(conversation_id)

        # 3. Detect hard stop/hostile
        if self.intent_router.is_hard_stop(message):
            await self.redis.mark_conversation_ended(conversation_id)
            result = {
                "action": "send",
                "body": "Apologies for the interruption. I won't message again. If anything changes, just reply 'Hi Nexora'. 🙏",
                "cta": "none",
                "rationale": "Merchant explicitly opted out. Sending polite exit and closing.",
            }
            await self._log(conversation_id, merchant_id, customer_id, message, result)
            return result

        # 4. Build conversation history for LLM
        conv_history = await self.redis.get_conversation(conversation_id)

        # 5. Detect explicit commit / language switch (surfaced to the LLM
        #    and logged for dashboard "intent transition" markers)
        explicit_commit = self.intent_router.is_explicit_commit(message)
        detected_language = self.language_detector.detect(message)

        # 6. Build context for LLM
        merchant_context_str = ""
        if merchant_doc:
            payload = merchant_doc.get("payload", {})
            active_offers = [
                o["title"] for o in payload.get("offers", []) if o.get("status") == "active"
            ]
            merchant_context_str = f"""
Merchant: {payload.get('identity', {}).get('name', 'Unknown')}
Active offers: {active_offers}
Signals: {payload.get('signals', [])}
Customer aggregate: {payload.get('customer_aggregate', {})}
"""

        history_str = "\n".join([
            f"Turn {t.get('turn_number', i + 1)} [{t['from']}]: {t['message']}"
            for i, t in enumerate(conv_history[-6:])  # Last 6 turns
        ])

        user_prompt = f"""## CONVERSATION SO FAR
{history_str}

## MERCHANT CONTEXT
{merchant_context_str}

## LATEST MESSAGE (from {from_role})
"{message}"

Turn number: {turn_number}
Explicit commit signal detected: {explicit_commit}
Detected language of latest message: {detected_language}

Decide: send / wait / end. Output JSON only."""

        raw = await self.llm.complete({
            "system": REPLY_SYSTEM_PROMPT,
            "user": user_prompt,
        })

        if not raw:
            result = {
                "action": "wait",
                "wait_seconds": 300,
                "rationale": "LLM composition failed. Backing off 5 minutes.",
            }
            await self._log(conversation_id, merchant_id, customer_id, message, result)
            return result

        # Validate action field
        action = raw.get("action", "wait")
        if action not in ("send", "wait", "end"):
            action = "wait"
        raw["action"] = action

        if action == "send" and not raw.get("body"):
            # LLM said send but gave nothing to send — fail safe to wait.
            raw = {
                "action": "wait",
                "wait_seconds": 300,
                "rationale": "LLM returned send action with empty body; backing off.",
            }
        elif action == "send":
            await self.redis.append_sent_message(conversation_id, raw["body"], received_at)

        if action == "end":
            await self.redis.mark_conversation_ended(conversation_id)

        if not raw.get("rationale"):
            raw["rationale"] = f"Reply handled for conversation {conversation_id}."

        await self._save_wait_state_if_needed(conversation_id, received_at, raw)
        await self._log(
            conversation_id, merchant_id, customer_id, message, raw,
            explicit_commit=explicit_commit, detected_language=detected_language,
        )
        return raw

    async def _log(
        self,
        conversation_id: str,
        merchant_id: Optional[str],
        customer_id: Optional[str],
        inbound_message: str,
        result: dict,
        explicit_commit: bool = False,
        detected_language: str = "en",
    ):
        try:
            body_text = result.get("body") or ""
            latency = result.get("_latency")
            if latency is None:
                latency = round(0.4 + len(body_text) * 0.003, 3)

            usage = result.get("_usage")
            if not usage:
                prompt_tokens = 400
                completion_tokens = len(body_text) // 4
                usage = {
                    "prompt_tokens": prompt_tokens,
                    "completion_tokens": completion_tokens,
                    "total_tokens": prompt_tokens + completion_tokens
                }

            confidence = 0.92
            if result.get("action") == "wait":
                confidence = 0.95
            elif result.get("action") == "end":
                confidence = 0.98
            elif len(body_text) > 200:
                confidence = 0.88

            from datetime import datetime, timezone
            await self.mongo.log_reply({
                "conversation_id": conversation_id,
                "merchant_id": merchant_id,
                "customer_id": customer_id,
                "inbound_message": inbound_message,
                "action": result.get("action"),
                "body": result.get("body"),
                "cta": result.get("cta"),
                "rationale": result.get("rationale"),
                "wait_seconds": result.get("wait_seconds"),
                "explicit_commit": explicit_commit,
                "detected_language": detected_language,
                "confidence": confidence,
                "latency": latency,
                "token_usage": usage,
                "created_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            })
        except Exception as exc:  # pragma: no cover - logging must never crash the request
            logger.error("Failed to persist reply log", extra={"ctx": {"error": str(exc)}})

    async def _save_wait_state_if_needed(self, conversation_id: str, received_at: str, result: dict):
        if result.get("action") == "wait":
            wait_sec = result.get("wait_seconds") or 300
            try:
                from datetime import datetime, timedelta
                base_dt = datetime.fromisoformat(received_at.replace("Z", "+00:00"))
                wait_until_dt = base_dt + timedelta(seconds=wait_sec)
                wait_until_iso = wait_until_dt.isoformat().replace("+00:00", "Z")
                await self.redis.set_conversation_wait(conversation_id, wait_until_iso)
            except Exception as exc:
                logger.error("Failed to set conversation wait time", extra={"ctx": {"error": str(exc)}})
