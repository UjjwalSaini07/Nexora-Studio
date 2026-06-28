import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from storage.mongo_store import MongoStore
from storage.redis_store import RedisStore
from logging_config import get_logger

logger = get_logger("nexora.demo_generator")

TEMPLATES = {
    "research_digest": {
        "body": "Dr. {owner}, JIDA's Oct issue landed. One item relevant to your high-risk adult patients — 2,100-patient trial showed 3-month fluoride recall cuts caries recurrence 38% better. Want me to pull it + draft a patient-ed WhatsApp? — JIDA Oct 2026 p.14",
        "rationale": "Anchored on 38% caries cut from JIDA trial for high-risk patients. Lever: specificity and effort externalization.",
        "cta": "open_ended",
        "send_as": "nexora"
    },
    "regulation_change": {
        "body": "Dr. {owner}, compliance update: New digital radiograph audit guidelines take effect by {deadline}. Non-compliance penalty applies. Want me to draft the compliance checklist for {name}?",
        "rationale": "Regulatory deadline of {deadline} is high urgency. Lever: loss aversion and effort externalization.",
        "cta": "binary_yes_no",
        "send_as": "nexora"
    },
    "perf_spike": {
        "body": "Dr. {owner}, your views spiked by {views_pct}% this week at {name}! Let's lock in this growth. Want me to run a campaign while this interest lasts?",
        "rationale": "Anchored on {views_pct}% increase in views. Lever: social proof and momentum.",
        "cta": "binary_yes_no",
        "send_as": "nexora"
    },
    "perf_dip": {
        "body": "Dr. {owner}, your CTR is at {ctr}% vs the {peer_ctr}% local peer average. Let's run a scaling promo for your cleaning offer to bridge the gap. Want me to draft it?",
        "rationale": "Anchored on CTR gap ({ctr}% vs peer {peer_ctr}%). Lever: loss aversion.",
        "cta": "binary_yes_no",
        "send_as": "nexora"
    },
    "seasonal_perf_dip": {
        "body": "Hi {owner}, performance is down slightly, but this fits the normal seasonal dip for salons in {city}. Let's focus on retention: want to run a winback campaign for your lapsed clients?",
        "rationale": "Reframed dip as normal seasonal lull. Lever: anxiety reduction + retention offer.",
        "cta": "binary_yes_no",
        "send_as": "nexora"
    },
    "recall_due": {
        "body": "Hello {customer_name}, it has been 6 months since your last scaling at {name}. We have open slots tomorrow: 10:00 AM or 4:00 PM. Reply 1 for 10am, 2 for 4pm to book.",
        "rationale": "Anchored on 6-month recall due for scaling. Lever: single binary commitment.",
        "cta": "multi_choice_slot",
        "send_as": "merchant_on_behalf"
    },
    "customer_lapsed_soft": {
        "body": "Hi {customer_name}, we haven't seen you at {name} in 3 months. We'd love to welcome you back with a special trial session on your next visit. Reply YES to book!",
        "rationale": "Anchored on Lapse soft (3 months). Lever: curiosity and low-friction return.",
        "cta": "binary_yes_no",
        "send_as": "merchant_on_behalf"
    },
    "customer_lapsed_hard": {
        "body": "Hi {customer_name}, we haven't seen you at {name} in 6+ months. We'd love to welcome you back with a special first-month deal on your next package. Reply YES to claim this offer!",
        "rationale": "Anchored on Lapse hard (6 months). Lever: structured win-back offer.",
        "cta": "binary_yes_no",
        "send_as": "merchant_on_behalf"
    },
    "winback_eligible": {
        "body": "Hi {customer_name}, we haven't seen you at {name} in 4 months. We'd love to welcome you back with a special offer on your next session. Reply YES to claim this offer!",
        "rationale": "Anchored on structured winback eligibility. Lever: structured win-back offer.",
        "cta": "binary_yes_no",
        "send_as": "merchant_on_behalf"
    },
    "trial_followup": {
        "body": "Hi {customer_name}, hope you enjoyed your trial class at {name}! Ready to book the full package? Reply YES to lock in your preferred time.",
        "rationale": "Anchored on trial session completion. Lever: effort externalization.",
        "cta": "binary_yes_no",
        "send_as": "merchant_on_behalf"
    },
    "wedding_package_followup": {
        "body": "Hi {customer_name}, your wedding day is in 30 days! Let's book your first pre-wedding skincare session at {name} for this Saturday. Reply YES to confirm.",
        "rationale": "Anchored on wedding prep timeline. Lever: commitment and scarcity.",
        "cta": "binary_yes_no",
        "send_as": "merchant_on_behalf"
    },
    "bridal_followup": {
        "body": "Hi {customer_name}, your big day is in 30 days! Let's book your first skin-prep session at {name} for this Saturday. Reply YES to confirm.",
        "rationale": "Anchored on bridal skin prep timeline. Lever: commitment and scarcity.",
        "cta": "binary_yes_no",
        "send_as": "merchant_on_behalf"
    },
    "renewal_due": {
        "body": "Hello {owner}, your Pro plan at {name} expires in 5 days. Keep your leads active. Want me to renew the plan now?",
        "rationale": "Anchored on plan renewal due in 5 days. Lever: loss aversion.",
        "cta": "binary_yes_no",
        "send_as": "nexora"
    },
    "dormant_with_nexora": {
        "body": "Hi {owner}, a new local research digest was just published. It has tips to increase bookings for {name}. Reply YES to see it.",
        "rationale": "Re-engagement nudge with a new research digest hook. Lever: reciprocity.",
        "cta": "binary_yes_no",
        "send_as": "nexora"
    },
    "milestone_reached": {
        "body": "Congratulations {owner}! {name} just reached 500 reviews on Google. Let's share this achievement with a post. Reply YES to generate it.",
        "rationale": "Anchored on crossing reviews milestone. Lever: social proof and celebration.",
        "cta": "open_ended",
        "send_as": "nexora"
    },
    "review_theme_emerged": {
        "body": "Hi {owner}, we noticed 3 recent negative reviews mentioning wait time for {name}. Let's address this. Want me to draft a Google reply?",
        "rationale": "Anchored on negative review theme (wait time). Lever: loss aversion.",
        "cta": "binary_yes_no",
        "send_as": "nexora"
    },
    "gbp_unverified": {
        "body": "Hi {owner}, your Google Business Profile for {name} is unverified, which ranks you lower. Want me to start the verification flow?",
        "rationale": "Anchored on unverified profile status. Lever: loss aversion.",
        "cta": "binary_yes_no",
        "send_as": "nexora"
    },
    "cde_opportunity": {
        "body": "Dr. {owner}, a CDE webinar is scheduled for tomorrow (offers 3 credits). Want the registration link?",
        "rationale": "Continuing education heads-up for dentists. Lever: peer recommendation.",
        "cta": "open_ended",
        "send_as": "nexora"
    },
    "appointment_tomorrow": {
        "body": "Hi {customer_name}, confirming your appointment at {name} tomorrow at 10:00 AM for dental checkup. Reply CONFIRM to keep or RESCHEDULE.",
        "rationale": "Appointment confirmation. Lever: commitment and no-show reduction.",
        "cta": "binary_confirm_cancel",
        "send_as": "merchant_on_behalf"
    },
    "category_seasonal": {
        "body": "Hi {owner}, wedding season is starting! Salons in {city} see 20% increase in blowouts. Let's run a campaign. Reply YES to start.",
        "rationale": "Seasonal campaign suggestion. Lever: social proof.",
        "cta": "binary_yes_no",
        "send_as": "nexora"
    },
    "festival_upcoming": {
        "body": "Happy early festival season {owner}! Let's launch a campaign for {name} to capture the festive rush. Reply YES to start.",
        "rationale": "Festival campaign nudge. Lever: social proof.",
        "cta": "binary_yes_no",
        "send_as": "nexora"
    },
    "competitor_opened": {
        "body": "Hi {owner}, a new competitor just opened within 1km of {name}. Let's secure your local ranking. Reply YES to see a comparison.",
        "rationale": "Competitor opening alert. Lever: curiosity and loss aversion.",
        "cta": "open_ended",
        "send_as": "nexora"
    },
    "curious_ask_due": {
        "body": "Hi {owner}, what has been your most popular service at {name} this week? I can turn your answer into a Google post. Reply to tell me!",
        "rationale": "Curiosity ask cadence. Lever: ask the merchant.",
        "cta": "open_ended",
        "send_as": "nexora"
    },
    "chronic_refill_due": {
        "body": "Hi {customer_name}, your chronic prescription refills are due by tomorrow. Reply YES to dispatch delivery from {name}.",
        "rationale": "Chronic prescription refill reminder. Lever: single binary commitment.",
        "cta": "binary_yes_no",
        "send_as": "merchant_on_behalf"
    },
    "supply_alert": {
        "body": "Urgent: batch recall for sub-potency. We have 14 affected customers at {name}. Want me to draft the notification message?",
        "rationale": "Urgent batch recall notification. Lever: safety precise.",
        "cta": "binary_yes_no",
        "send_as": "nexora"
    },
    "ipl_match_today": {
        "body": "Hi {owner}, IPL match in {city} today! Expect delivery orders to surge. Let's activate a match promo for {name}. Reply YES to start.",
        "rationale": "IPL match delivery promo recommendation. Lever: social proof.",
        "cta": "binary_yes_no",
        "send_as": "nexora"
    },
    "active_planning_intent": {
        "body": "Hi {owner}, here is the draft menu for the thali planning at {name}. Reply CONFIRM to launch it.",
        "rationale": "Action mode follow-up menu draft. Lever: effort externalization.",
        "cta": "binary_confirm_cancel",
        "send_as": "nexora"
    }
}

async def ensure_demo_data(mongo: MongoStore, redis: RedisStore):
    """If actions_log is empty in MongoDB, populate it with deterministic demo analytics."""
    actions_count = await mongo.actions_log.count_documents({})
    if actions_count > 0:
        return

    logger.info("MongoDB actions_log is empty. Seeding deterministic demo data...")
    
    # Load test pairs
    expanded_dir = Path(__file__).parent.parent.parent / "expanded"
    pairs_file = expanded_dir / "test_pairs.json"
    if not pairs_file.exists():
        logger.warning(f"test_pairs.json not found at {pairs_file}, skipping demo seed.")
        return

    try:
        pairs_data = json.loads(pairs_file.read_text(encoding="utf-8-sig"))
        pairs = pairs_data.get("pairs", [])
    except Exception as exc:
        logger.error(f"Failed to read test_pairs.json: {exc}")
        return

    # Seed suppressions
    demo_suppressions = [
        "research:dentists:2026-W17",
        "compliance:dentists:2026-W18",
        "perf_dip:m_002_bharat_dentist_mumbai",
        "appointment_tomorrow:c_075_aditya_for_m_019_karim_salon_lucknow"
    ]
    for key in demo_suppressions:
        await redis.set_suppression(key)
        await mongo.log_suppression(key)

    # Let's prepare a deterministic base time for our logs
    base_time = datetime.now(timezone.utc) - timedelta(hours=18)

    # We will log ticks, actions, and replies
    ticks = []
    actions_to_log = []
    replies_to_log = []

    # Process pairs and generate data
    for i, pair in enumerate(pairs):
        test_id = pair.get("test_id", f"T{i}")
        trg_id = pair.get("trigger_id")
        m_id = pair.get("merchant_id")
        c_id = pair.get("customer_id")

        # Fetch contexts from Mongo
        trigger_doc = await mongo.get_context("trigger", trg_id)
        merchant_doc = await mongo.get_context("merchant", m_id)
        if not trigger_doc or not merchant_doc:
            continue

        trigger = trigger_doc["payload"]
        merchant = merchant_doc["payload"]
        
        customer = None
        if c_id:
            customer_doc = await mongo.get_context("customer", c_id)
            if customer_doc:
                customer = customer_doc["payload"]

        # Determine category and attributes
        category = merchant.get("category_slug", "dentists")
        owner = merchant.get("identity", {}).get("owner_first_name", "Owner")
        m_name = merchant.get("identity", {}).get("name", "Merchant")
        city = merchant.get("identity", {}).get("city", "Delhi")

        t_kind = trigger.get("kind", "research_digest")
        template_info = TEMPLATES.get(t_kind)
        if not template_info:
            template_info = TEMPLATES["curious_ask_due"]

        # Format body message
        deadline = trigger.get("payload", {}).get("deadline_iso", "2026-05-15")
        views_pct = int(merchant.get("performance", {}).get("delta_7d", {}).get("views_pct", 0.15) * 100)
        ctr = round(merchant.get("performance", {}).get("ctr", 0.02) * 100, 1)
        peer_ctr = 3.0
        c_name = customer.get("identity", {}).get("name", "Customer") if customer else "Customer"

        body = template_info["body"].format(
            owner=owner,
            name=m_name,
            deadline=deadline,
            views_pct=views_pct,
            ctr=ctr,
            peer_ctr=peer_ctr,
            city=city,
            customer_name=c_name,
            months=3,
            offer="₹299 scaling",
            plan=merchant.get("subscription", {}).get("plan", "Pro"),
            days=trigger.get("payload", {}).get("days_remaining", 5),
            milestone=trigger.get("payload", {}).get("count", 500),
            count=trigger.get("payload", {}).get("count", 3),
            theme=trigger.get("payload", {}).get("theme", "wait time"),
            title="Continuing Dental Education Seminar",
            credits=3,
            time="10:00 AM",
            service="scaling",
            pct=20,
            distance="1km",
            date="tomorrow",
            batch="B_988",
            seasonal_event="summer lull"
        )

        rationale = template_info["rationale"].format(
            deadline=deadline,
            views_pct=views_pct,
            ctr=ctr,
            peer_ctr=peer_ctr,
            days=5,
            theme="wait time",
            count=3
        )

        # Generate conversation ID
        customer_part = f"_{c_id}" if c_id else ""
        conv_id = f"conv_{m_id}_{t_kind}{customer_part}"

        # Create action
        action_time = base_time + timedelta(minutes=i * 20)
        action_time_str = action_time.isoformat().replace("+00:00", "Z")

        # Deterministic confidence, latency, tokens
        urgency = trigger.get("urgency", 3)
        confidence = round(0.88 + (urgency * 0.01) - (0.02 if len(body) > 250 else 0), 2)
        latency = round(0.5 + (i % 5) * 0.15 + len(body) * 0.001, 3)
        token_usage = {
            "prompt_tokens": 400 + (i % 3) * 20,
            "completion_tokens": len(body) // 4,
            "total_tokens": 400 + (i % 3) * 20 + len(body) // 4
        }

        action_doc = {
            "conversation_id": conv_id,
            "merchant_id": m_id,
            "customer_id": c_id,
            "send_as": template_info["send_as"],
            "trigger_id": trg_id,
            "template_name": f"nexora_{t_kind}_v1",
            "template_params": [owner, body[:80], template_info["cta"]],
            "body": body,
            "cta": template_info["cta"],
            "suppression_key": trigger.get("suppression_key", f"suppress:{trg_id}"),
            "rationale": rationale,
            "logged_at": action_time_str,
            "created_at": action_time_str,
            "merchant": m_name,
            "trigger": t_kind,
            "category": category,
            "confidence": confidence,
            "decision_reason": rationale,
            "selected_template": f"nexora_{t_kind}_v1",
            "message": body,
            "latency": latency,
            "token_usage": token_usage,
        }

        actions_to_log.append(action_doc)

        # Record this action turn in Redis for anti-repetition / consistency
        await redis.append_sent_message(conv_id, body, action_time_str)

        # For select conversations, simulate turns
        if i % 2 == 0:  # Multi-turn conversation
            # Turn 1: Bot sent (handled by action)
            # Turn 2: User responds
            reply_user_time = action_time + timedelta(minutes=5)
            reply_user_time_str = reply_user_time.isoformat().replace("+00:00", "Z")

            inbound_message = "Yes, please draft it"
            if template_info["cta"] == "binary_confirm_cancel":
                inbound_message = "CONFIRM"
            elif template_info["cta"] == "multi_choice_slot":
                inbound_message = "Reply 1"
            elif template_info["cta"] == "open_ended":
                inbound_message = "How can we do this?"

            await redis.append_turn(conv_id, {
                "from": "merchant" if template_info["send_as"] == "nexora" else "customer",
                "message": inbound_message,
                "received_at": reply_user_time_str,
                "turn_number": 2
            })

            # Turn 3: Bot responds (reply)
            reply_bot_time = action_time + timedelta(minutes=8)
            reply_bot_time_str = reply_bot_time.isoformat().replace("+00:00", "Z")

            bot_reply_body = "Perfect! I've scheduled it for you. Let me know if you need to adjust anything."
            if template_info["cta"] == "binary_yes_no":
                bot_reply_body = f"Here is the draft campaign: 'Enjoy 20% off for festival bookings!'. Reply CONFIRM to send."
            elif template_info["cta"] == "multi_choice_slot":
                bot_reply_body = "Confirmed! I've booked your slot. See you soon!"

            bot_reply_rationale = "User committed. Sending confirmation / next step draft. Lever: commitment."
            bot_reply_action = "send"
            if i % 6 == 0:
                bot_reply_action = "end"
                bot_reply_body = "Closed. Let me know if you need help later!"
            elif i % 8 == 0:
                bot_reply_action = "wait"
                bot_reply_body = None

            reply_doc = {
                "conversation_id": conv_id,
                "merchant_id": m_id,
                "customer_id": c_id,
                "inbound_message": inbound_message,
                "action": bot_reply_action,
                "body": bot_reply_body,
                "cta": "none" if bot_reply_action == "end" else "binary_confirm_cancel",
                "rationale": bot_reply_rationale,
                "wait_seconds": 14400 if bot_reply_action == "wait" else None,
                "explicit_commit": inbound_message in ("YES", "CONFIRM", "Yes, please draft it"),
                "detected_language": "en",
                "confidence": 0.95 if bot_reply_action == "wait" else 0.92,
                "latency": round(0.6 + (i % 3) * 0.1, 3),
                "token_usage": {
                    "prompt_tokens": 380,
                    "completion_tokens": len(bot_reply_body or "") // 4,
                    "total_tokens": 380 + len(bot_reply_body or "") // 4
                },
                "logged_at": reply_bot_time_str,
                "created_at": reply_bot_time_str,
            }
            replies_to_log.append(reply_doc)

            if bot_reply_body:
                await redis.append_sent_message(conv_id, bot_reply_body, reply_bot_time_str)
            if bot_reply_action == "end":
                await redis.mark_conversation_ended(conv_id)

    # Insert all generated actions
    if actions_to_log:
        await mongo.actions_log.insert_many(actions_to_log)
    # Insert all generated replies
    if replies_to_log:
        await mongo.replies_log.insert_many(replies_to_log)

    # Generate a few ticks to populate ticks table
    for t_idx in range(5):
        tick_time = base_time + timedelta(hours=t_idx * 3)
        tick_time_str = tick_time.isoformat().replace("+00:00", "Z")
        t_actions = [
            a for a in actions_to_log 
            if datetime.fromisoformat(a["logged_at"].replace("Z", "+00:00")) <= datetime.fromisoformat(tick_time_str.replace("Z", "+00:00"))
        ][-3:]

        tick_doc = {
            "now": tick_time_str,
            "available_triggers": [a["trigger_id"] for a in t_actions],
            "actions": [{
                "conversation_id": a["conversation_id"],
                "merchant_id": a["merchant_id"],
                "customer_id": a["customer_id"],
                "send_as": a["send_as"],
                "trigger_id": a["trigger_id"],
                "template_name": a["template_name"],
                "template_params": a["template_params"],
                "body": a["body"],
                "cta": a["cta"],
                "suppression_key": a["suppression_key"],
                "rationale": a["rationale"],
            } for a in t_actions],
            "created_at": tick_time_str
        }
        await mongo.ticks_log.insert_one(tick_doc)

    logger.info(f"Demo seeding complete: {len(actions_to_log)} actions, {len(replies_to_log)} replies generated.")
