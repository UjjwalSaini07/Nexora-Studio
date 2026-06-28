import asyncio
from composer.engine import EngagementComposer
from storage.redis_store import RedisStore
from storage.mongo_store import MongoStore
from models.context import TriggerContext
from config import DEMO_MODE

async def main():
    print(f"DEMO_MODE value in config: {DEMO_MODE}")
    redis = RedisStore()
    mongo = MongoStore()
    
    composer = EngagementComposer(redis, mongo)
    
    # Let's test T07 (trg_019_chronic_refill_grandfather)
    trigger_id = "trg_019_chronic_refill_grandfather"
    print(f"\n--- Testing trigger: {trigger_id} ---")
    doc = await mongo.get_context("trigger", trigger_id)
    if not doc:
        print(f"Trigger {trigger_id} not found in MongoDB context collection!")
        return
        
    trigger = TriggerContext(**doc["payload"])
    print(f"Trigger fields:")
    print(f"  kind: {trigger.kind}")
    print(f"  suppression_key: {trigger.suppression_key}")
    print(f"  expires_at: {trigger.expires_at}")
    
    # Check if suppressed
    is_sup = await redis.is_suppressed(trigger.suppression_key)
    print(f"Is key suppressed in Redis? {is_sup}")
    
    # Run the assembler
    contexts = await composer.assembler.assemble(trigger)
    if not contexts:
        print("Assembler returned None! One of the contexts (category, merchant, customer) is missing!")
        return
    category, merchant, customer = contexts
    print(f"Assembler succeeded:")
    print(f"  category: {category.slug if category else None}")
    print(f"  merchant: {merchant.merchant_id if merchant else None}")
    print(f"  customer: {customer.customer_id if customer else None}")
    
    # Build prompt
    prompt = composer.prompt_builder.build(
        category=category,
        merchant=merchant,
        trigger=trigger,
        customer=customer,
        now_iso="2026-04-27T23:00:00Z"
    )
    print("Built prompt successfully.")
    
    # Call LLM
    print("Calling LLM...")
    raw_response = await composer.llm.complete(prompt)
    print(f"LLM Raw Response: {raw_response}")
    
    if not raw_response:
        print("LLM returned empty response!")
        return
        
    # Validate
    validated = composer.validator.validate(
        raw_response, trigger, merchant, category,
        previously_sent_bodies=[],
    )
    print(f"Validation Result: {validated}")

if __name__ == "__main__":
    asyncio.run(main())
