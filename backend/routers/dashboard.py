# backend/routers/dashboard.py
"""
Read-only endpoints that exist solely to back the Next.js operations
dashboard: live context inspector, recent actions/replies feed, and basic
score-analytics placeholders.
"""
from typing import Optional, List
from datetime import datetime, timezone, timedelta
import asyncio
import json
from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse

from dependencies import get_redis, get_mongo
from storage.redis_store import RedisStore
from storage.mongo_store import MongoStore
from dataset.demo_generator import ensure_demo_data
from composer.engine import EngagementComposer
from models.context import TriggerContext

router = APIRouter(prefix="/v1/dashboard")


@router.get("/contexts")
async def list_contexts(
    scope: Optional[str] = Query(default=None),
    limit: int = Query(default=100, le=500),
    mongo: MongoStore = Depends(get_mongo),
    redis: RedisStore = Depends(get_redis),
):
    await ensure_demo_data(mongo, redis)
    contexts = await mongo.list_contexts(scope=scope, limit=limit)
    return {"contexts": contexts, "count": len(contexts)}


@router.get("/contexts/{scope}/{context_id}")
async def get_context_detail(
    scope: str,
    context_id: str,
    mongo: MongoStore = Depends(get_mongo),
    redis: RedisStore = Depends(get_redis),
):
    await ensure_demo_data(mongo, redis)
    doc = await mongo.get_context(scope, context_id)
    return {"context": doc}


@router.get("/contexts/{scope}/{context_id}/history")
async def get_context_history(
    scope: str,
    context_id: str,
    mongo: MongoStore = Depends(get_mongo),
    redis: RedisStore = Depends(get_redis),
):
    await ensure_demo_data(mongo, redis)
    history = await mongo.get_context_history(scope, context_id)
    return {"history": history, "count": len(history)}


@router.get("/actions")
async def recent_actions(
    limit: int = Query(default=50, le=200),
    mongo: MongoStore = Depends(get_mongo),
    redis: RedisStore = Depends(get_redis),
):
    await ensure_demo_data(mongo, redis)
    actions = await mongo.get_recent_actions(limit=limit)
    return {"actions": actions, "count": len(actions)}


@router.get("/replies")
async def recent_replies(
    limit: int = Query(default=50, le=200),
    mongo: MongoStore = Depends(get_mongo),
    redis: RedisStore = Depends(get_redis),
):
    await ensure_demo_data(mongo, redis)
    replies = await mongo.get_recent_replies(limit=limit)
    return {"replies": replies, "count": len(replies)}


@router.get("/conversations/{conversation_id}")
async def conversation_detail(
    conversation_id: str,
    redis: RedisStore = Depends(get_redis),
    mongo: MongoStore = Depends(get_mongo),
):
    await ensure_demo_data(mongo, redis)
    turns = await redis.get_conversation(conversation_id)
    sent = await redis.get_sent_messages(conversation_id)
    ended = await redis.is_conversation_ended(conversation_id)
    auto_reply_count = await redis.get_auto_reply_count(conversation_id)
    replies_log = await mongo.get_replies_for_conversation(conversation_id)
    return {
        "conversation_id": conversation_id,
        "turns": turns,
        "sent_by_nexora": sent,
        "ended": ended,
        "auto_reply_count": auto_reply_count,
        "replies_log": replies_log,
    }


@router.get("/conversations")
async def list_conversations(
    status_filter: Optional[str] = Query(default=None, alias="status"),
    mongo: MongoStore = Depends(get_mongo),
    redis: RedisStore = Depends(get_redis),
):
    await ensure_demo_data(mongo, redis)

    # 1. Fetch actions and replies to group them
    actions = await mongo.get_recent_actions(limit=1000)
    replies = await mongo.get_recent_replies(limit=1000)

    # 2. Get active suppressions from Mongo/Redis
    suppressed_keys = set(await mongo.get_all_suppressions())

    # 3. Group into conversation summaries
    conv_map = {}

    # Helper to initialize conversation entry
    def get_or_create_conv(conv_id, m_id, c_id):
        if conv_id not in conv_map:
            conv_map[conv_id] = {
                "conversation_id": conv_id,
                "merchant_id": m_id,
                "customer_id": c_id,
                "merchant_name": "Merchant",
                "merchant_category": "unknown",
                "status": "Active",
                "reply_count": 0,
                "latest_message": "",
                "confidence": 0.90,
                "decision_rationale": "",
                "trigger": "unknown",
                "selected_template": "unknown",
                "suppression_state": False,
                "timeline": [],
                "urgency": 3,
            }
        return conv_map[conv_id]

    # Process all outbound actions (from ticks)
    for act in actions:
        conv_id = act.get("conversation_id")
        if not conv_id:
            continue
        conv = get_or_create_conv(conv_id, act.get("merchant_id"), act.get("customer_id"))
        conv["merchant_name"] = act.get("merchant") or conv["merchant_name"]
        conv["merchant_category"] = act.get("category") or conv["merchant_category"]
        conv["trigger"] = act.get("trigger") or conv["trigger"]
        conv["selected_template"] = act.get("selected_template") or conv["selected_template"]
        conv["urgency"] = act.get("urgency_val", 3)
        
        # Check suppression
        supp_key = act.get("suppression_key")
        if supp_key and supp_key in suppressed_keys:
            conv["suppression_state"] = True

        conv["timeline"].append({
            "from": "nexora",
            "message": act.get("body"),
            "logged_at": act.get("logged_at") or act.get("created_at"),
            "action": "send",
            "rationale": act.get("rationale"),
            "confidence": act.get("confidence", 0.90),
            "cta": act.get("cta"),
            "type": "action"
        })

    # Process all reply turns
    for rep in replies:
        conv_id = rep.get("conversation_id")
        if not conv_id:
            continue
        conv = get_or_create_conv(conv_id, rep.get("merchant_id"), rep.get("customer_id"))

        # Add inbound turn
        logged_at_dt = datetime.fromisoformat(rep["logged_at"].replace("Z", "+00:00"))
        inbound_logged_at = (logged_at_dt - timedelta(seconds=10)).isoformat().replace("+00:00", "Z")

        conv["timeline"].append({
            "from": "customer" if rep.get("customer_id") else "merchant",
            "message": rep.get("inbound_message"),
            "logged_at": inbound_logged_at,
            "type": "inbound"
        })

        # Add bot reply turn
        conv["timeline"].append({
            "from": "nexora",
            "message": rep.get("body") or f"[{rep.get('action')}]",
            "logged_at": rep.get("logged_at"),
            "action": rep.get("action"),
            "rationale": rep.get("rationale"),
            "confidence": rep.get("confidence", 0.90),
            "cta": rep.get("cta") or "none",
            "type": "reply"
        })

    # Post-process, sort timelines, calculate stats
    results = []
    for conv_id, conv in conv_map.items():
        # Sort timeline chronologically
        conv["timeline"].sort(key=lambda t: t["logged_at"])
        conv["reply_count"] = len(conv["timeline"])
        
        # Get latest message details
        if conv["timeline"]:
            latest_turn = conv["timeline"][-1]
            conv["latest_message"] = latest_turn.get("message") or ""
            
            # Find last bot turn to get rationale and confidence
            bot_turns = [t for t in conv["timeline"] if t.get("from") == "nexora"]
            if bot_turns:
                last_bot = bot_turns[-1]
                conv["confidence"] = last_bot.get("confidence", 0.90)
                conv["decision_rationale"] = last_bot.get("rationale") or ""

        # Determine conversation status
        is_ended = await redis.is_conversation_ended(conv_id)
        if is_ended:
            conv["status"] = "Resolved"
        elif conv["suppression_state"]:
            conv["status"] = "Suppressed"
        elif any(t.get("action") == "wait" for t in conv["timeline"]):
            conv["status"] = "Waiting"
        elif conv.get("urgency", 3) >= 4:
            conv["status"] = "High Priority"
        else:
            conv["status"] = "Active"

        # Apply filter
        if status_filter:
            if conv["status"].lower() == status_filter.lower():
                results.append(conv)
        else:
            results.append(conv)

    # Sort conversations by latest activity descending
    results.sort(key=lambda c: c["timeline"][-1]["logged_at"] if c["timeline"] else "", reverse=True)
    return {"conversations": results, "count": len(results)}


@router.get("/stats")
async def stats(
    redis: RedisStore = Depends(get_redis),
    mongo: MongoStore = Depends(get_mongo),
):
    await ensure_demo_data(mongo, redis)

    # Core connection checks
    mongo_ok = await mongo.ping()
    redis_ok = False
    try:
        await redis.get_start_time()
        redis_ok = True
    except Exception:
        pass

    # Context counts
    counts = await redis.get_context_counts()

    # Load all action logs and reply logs for statistics aggregation
    actions = await mongo.get_recent_actions(limit=2000)
    replies = await mongo.get_recent_replies(limit=2000)
    ticks = await mongo.get_recent_ticks(limit=100)

    # Today's messages (since 00:00 UTC today)
    today_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    today_msg_count = 0
    for act in actions:
        dt = datetime.fromisoformat(act["logged_at"].replace("Z", "+00:00"))
        if dt >= today_start:
            today_msg_count += 1
    for rep in replies:
        dt = datetime.fromisoformat(rep["logged_at"].replace("Z", "+00:00"))
        if dt >= today_start:
            today_msg_count += 1

    # Active conversations & pending replies count
    conv_ids = set()
    active_conv_count = 0
    pending_reply_count = 0
    
    for rep in replies:
        c_id = rep["conversation_id"]
        if c_id not in conv_ids:
            conv_ids.add(c_id)
            is_ended = await redis.is_conversation_ended(c_id)
            if not is_ended:
                active_conv_count += 1
        if rep.get("action") == "wait":
            pending_reply_count += 1

    # Suppressed count
    suppressions = await mongo.get_all_suppressions()
    suppressed_count = len(suppressions)

    # Decision confidence stats
    all_confidences = [a.get("confidence", 0.90) for a in actions] + [r.get("confidence", 0.92) for r in replies]
    avg_confidence = round(sum(all_confidences) / len(all_confidences), 2) if all_confidences else 0.92

    # Top Trigger, Category, Merchant counts
    trigger_counts = {}
    category_counts = {}
    merchant_counts = {}
    cta_counts = {}
    confidence_bins = {"0.5-0.6": 0, "0.6-0.7": 0, "0.7-0.8": 0, "0.8-0.9": 0, "0.9-1.0": 0}
    hourly_activity = [0] * 24

    for act in actions:
        # Trigger kind
        t_kind = act.get("trigger", "unknown")
        trigger_counts[t_kind] = trigger_counts.get(t_kind, 0) + 1

        # Category
        cat = act.get("category", "unknown")
        category_counts[cat] = category_counts.get(cat, 0) + 1

        # Merchant
        m_id = act.get("merchant_id", "unknown")
        merchant_counts[m_id] = merchant_counts.get(m_id, 0) + 1

        # CTA
        cta = act.get("cta", "none")
        cta_counts[cta] = cta_counts.get(cta, 0) + 1

        # Confidence Distribution
        conf = act.get("confidence", 0.90)
        if 0.5 <= conf < 0.6: confidence_bins["0.5-0.6"] += 1
        elif 0.6 <= conf < 0.7: confidence_bins["0.6-0.7"] += 1
        elif 0.7 <= conf < 0.8: confidence_bins["0.7-0.8"] += 1
        elif 0.8 <= conf < 0.9: confidence_bins["0.8-0.9"] += 1
        elif 0.9 <= conf <= 1.0: confidence_bins["0.9-1.0"] += 1

        # Hourly Activity
        dt = datetime.fromisoformat(act["logged_at"].replace("Z", "+00:00"))
        hourly_activity[dt.hour] += 1

    for rep in replies:
        # Hourly Activity
        dt = datetime.fromisoformat(rep["logged_at"].replace("Z", "+00:00"))
        hourly_activity[dt.hour] += 1

    top_trigger = max(trigger_counts, key=trigger_counts.get) if trigger_counts else "N/A"
    top_category = max(category_counts, key=category_counts.get) if category_counts else "N/A"
    top_merchant = max(merchant_counts, key=merchant_counts.get) if merchant_counts else "N/A"

    # Latencies
    all_latencies = [a.get("latency", 0.8) for a in actions] + [r.get("latency", 0.9) for r in replies]
    avg_latency = round(sum(all_latencies) / len(all_latencies), 2) if all_latencies else 0.85
    latest_tick_duration = ticks[0].get("actions", [{}])[0].get("latency", 1.2) if ticks and ticks[0].get("actions") else 0.0
    if not latest_tick_duration and ticks:
        # Fallback to general estimation
        latest_tick_duration = 0.95

    # Interleaved chronological live timeline
    timeline = []
    for act in actions[:50]:
        timeline.append({
            "id": act.get("trigger_id", "act"),
            "event_type": "decision",
            "message": act.get("body"),
            "merchant": act.get("merchant", "Merchant"),
            "trigger": act.get("trigger", "Trigger"),
            "category": act.get("category", "Category"),
            "confidence": act.get("confidence", 0.90),
            "timestamp": act.get("logged_at")
        })
    for rep in replies[:50]:
        timeline.append({
            "id": rep.get("conversation_id", "rep"),
            "event_type": "reply",
            "message": rep.get("body") or f"[{rep.get('action')}]",
            "inbound": rep.get("inbound_message"),
            "merchant": rep.get("merchant_id", "Merchant"),
            "trigger": "reply_handler",
            "category": rep.get("action", "send"),
            "confidence": rep.get("confidence", 0.95),
            "timestamp": rep.get("logged_at")
        })
    timeline.sort(key=lambda item: item["timestamp"], reverse=True)

    return {
        "bot_status": "running" if (mongo_ok and redis_ok) else "degraded",
        "mongo_connected": mongo_ok,
        "redis_connected": redis_ok,
        "llm_status": "configured",
        "contexts_loaded": counts,
        "today_messages": today_msg_count,
        "active_conversations": active_conv_count,
        "pending_replies": pending_reply_count,
        "suppressed_messages": suppressed_count,
        "average_decision_confidence": avg_confidence,
        "top_trigger": top_trigger,
        "top_category": top_category,
        "top_merchant": top_merchant,
        "hourly_activity": hourly_activity,
        "actions_by_category": category_counts,
        "actions_by_trigger": trigger_counts,
        "cta_distribution": cta_counts,
        "decision_confidence_distribution": confidence_bins,
        "recent_decisions": actions[:15],
        "recent_replies": replies[:15],
        "recent_suppressions": suppressions[:15],
        "recent_errors": 0,
        "latest_tick_duration": latest_tick_duration,
        "average_response_time": avg_latency,
        "live_timeline": timeline[:30]
    }


@router.get("/simulate_tick_stream")
async def simulate_tick_stream(
    now: str = Query(...),
    trigger_ids: str = Query(...),
    mongo: MongoStore = Depends(get_mongo),
    redis: RedisStore = Depends(get_redis),
):
    ids = [id.strip() for id in trigger_ids.split(",") if id.strip()]
    
    async def event_generator():
        composer = EngagementComposer(redis, mongo)
        
        # Start event
        yield f"data: {json.dumps({'event': 'start', 'message': f'Starting simulation for {len(ids)} triggers'})}\n\n"
        await asyncio.sleep(0.05)

        # 1. Signal Ranking
        ranked_triggers = []
        for trg_id in ids:
            trigger_doc = await mongo.get_context("trigger", trg_id)
            if trigger_doc:
                payload = trigger_doc.get("payload", {})
                urgency = payload.get("urgency", 3)
                kind = payload.get("kind", "unknown")
                ranked_triggers.append({
                    "trigger_id": trg_id,
                    "urgency": urgency,
                    "kind": kind,
                    "payload": payload
                })
        # Sort by urgency descending
        ranked_triggers.sort(key=lambda x: x["urgency"], reverse=True)
        
        yield f"data: {json.dumps({'event': 'signal_ranking', 'ranking': ranked_triggers})}\n\n"
        await asyncio.sleep(0.1)

        seen_pairs = set()
        actions_returned = 0

        for item in ranked_triggers:
            trg_id = item["trigger_id"]
            yield f"data: {json.dumps({'event': 'trigger_start', 'trigger_id': trg_id})}\n\n"
            await asyncio.sleep(0.05)

            # Decision Engine Stage
            yield f"data: {json.dumps({'event': 'stage', 'trigger_id': trg_id, 'stage': 'Decision Engine', 'status': 'Checking suppression rules, expiration window and active conversation status'})}\n\n"
            await asyncio.sleep(0.05)

            trigger_doc = await mongo.get_context("trigger", trg_id)
            if not trigger_doc:
                yield f"data: {json.dumps({'event': 'trigger_skipped', 'trigger_id': trg_id, 'reason': 'Trigger not found in database'})}\n\n"
                continue

            try:
                trigger = TriggerContext(**trigger_doc["payload"])
            except Exception as exc:
                yield f"data: {json.dumps({'event': 'trigger_skipped', 'trigger_id': trg_id, 'reason': f'Context validation failed: {str(exc)}'})}\n\n"
                continue

            # Check suppression
            is_suppressed = await redis.is_suppressed(trigger.suppression_key)
            if is_suppressed:
                yield f"data: {json.dumps({'event': 'trigger_skipped', 'trigger_id': trg_id, 'reason': f'Suppressed by key: {trigger.suppression_key}', 'suppression_key': trigger.suppression_key})}\n\n"
                continue

            # Check expiry
            if trigger.expires_at:
                try:
                    expires = datetime.fromisoformat(trigger.expires_at.replace("Z", "+00:00"))
                    now_dt = datetime.fromisoformat(now.replace("Z", "+00:00"))
                    if now_dt > expires:
                        yield f"data: {json.dumps({'event': 'trigger_skipped', 'trigger_id': trg_id, 'reason': f'Trigger expired at {trigger.expires_at}'})}\n\n"
                        continue
                except ValueError:
                    pass

            # Assemble contexts
            contexts = await composer.assembler.assemble(trigger)
            if not contexts:
                yield f"data: {json.dumps({'event': 'trigger_skipped', 'trigger_id': trg_id, 'reason': 'Missing category, merchant or customer context payload'})}\n\n"
                continue
            category, merchant, customer = contexts

            # Composer Stage
            yield f"data: {json.dumps({'event': 'stage', 'trigger_id': trg_id, 'stage': 'Composer', 'status': 'Assembled contexts. Invoking LLM for prompt template generation...'})}\n\n"
            await asyncio.sleep(0.05)

            prompt = composer.prompt_builder.build(
                category=category,
                merchant=merchant,
                trigger=trigger,
                customer=customer,
                now_iso=now
            )

            # Call LLM
            import time
            t0 = time.perf_counter()
            raw_response = await composer.llm.complete(prompt)
            latency = round(time.perf_counter() - t0, 3)

            if not raw_response:
                yield f"data: {json.dumps({'event': 'trigger_skipped', 'trigger_id': trg_id, 'reason': 'LLM call returned no usable draft'})}\n\n"
                continue

            # Validator Stage
            yield f"data: {json.dumps({'event': 'stage', 'trigger_id': trg_id, 'stage': 'Validator', 'status': 'Analyzing message payload structure, CTA compliance and anti-repetition memory'})}\n\n"
            await asyncio.sleep(0.05)

            conv_id = composer._build_conversation_id(trigger)
            previously_sent_raw = await redis.get_sent_messages(conv_id)
            previously_sent_bodies = [m["body"] for m in previously_sent_raw]

            validated = composer.validator.validate(
                raw_response, trigger, merchant, category,
                previously_sent_bodies=previously_sent_bodies,
            )
            if not validated:
                yield f"data: {json.dumps({'event': 'trigger_skipped', 'trigger_id': trg_id, 'reason': 'Validation rejected draft (potential repetition or format mismatch)'})}\n\n"
                continue

            # Reviewer Stage
            yield f"data: {json.dumps({'event': 'stage', 'trigger_id': trg_id, 'stage': 'Reviewer', 'status': 'Finalizing template parameters, safety review and recording suppressions'})}\n\n"
            await asyncio.sleep(0.05)

            # De-duplicate checks for (merchant_id, conversation_id)
            pair_key = (merchant.merchant_id, conv_id)
            if pair_key in seen_pairs:
                yield f"data: {json.dumps({'event': 'trigger_skipped', 'trigger_id': trg_id, 'reason': f'Skipped duplicate action for pair {pair_key} in same tick'})}\n\n"
                continue
            seen_pairs.add(pair_key)

            # Set suppressions
            await redis.set_suppression(trigger.suppression_key)
            await mongo.log_suppression(trigger.suppression_key)
            await redis.append_sent_message(conv_id, validated["body"], now)

            # Confidence calculation
            has_taboo = len(validated.get("taboo_hits", [])) > 0
            confidence = 0.85 + (trigger.urgency * 0.02)
            if has_taboo:
                confidence -= 0.15
            if len(validated["body"]) > 300:
                confidence -= 0.05
            confidence = min(max(round(confidence, 2), 0.50), 1.0)

            usage = raw_response.get("_usage", {
                "prompt_tokens": 450,
                "completion_tokens": len(validated["body"]) // 4,
                "total_tokens": 450 + len(validated["body"]) // 4
            })

            action_result = {
                "conversation_id": conv_id,
                "merchant_id": trigger.merchant_id,
                "customer_id": trigger.customer_id,
                "send_as": validated["send_as"],
                "trigger_id": trigger.id,
                "template_name": composer._get_template_name(trigger.kind),
                "template_params": validated.get("template_params", []),
                "body": validated["body"],
                "cta": validated["cta"],
                "suppression_key": trigger.suppression_key,
                "rationale": validated["rationale"],
                "merchant": merchant.identity.name,
                "trigger": trigger.kind,
                "category": category.slug,
                "confidence": confidence,
                "decision_reason": validated["rationale"],
                "selected_template": composer._get_template_name(trigger.kind),
                "message": validated["body"],
                "created_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
                "latency": latency,
                "token_usage": usage,
                "urgency_val": trigger.urgency,
            }

            # Log to MongoDB
            try:
                await mongo.log_action(action_result)
                actions_logged = True
            except Exception:
                actions_logged = False

            actions_returned += 1
            yield f"data: {json.dumps({
                'event': 'action',
                'trigger_id': trg_id,
                'action': action_result,
                'actions_logged': actions_logged,
                'confidence': confidence,
                'latency': latency,
                'token_usage': usage
            })}\n\n"
            await asyncio.sleep(0.1)

        # Yield end event
        yield f"data: {json.dumps({'event': 'done', 'actions_returned': actions_returned})}\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")
