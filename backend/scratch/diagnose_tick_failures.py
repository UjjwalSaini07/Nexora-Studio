# backend/scratch/diagnose_tick_failures.py
import asyncio
from motor.motor_asyncio import AsyncIOMotorClient
from redis.asyncio import Redis

async def main():
    mongo_client = AsyncIOMotorClient("mongodb://localhost:27017")
    db = mongo_client["nexorabot"]
    
    redis_client = Redis.from_url("redis://localhost:6379", decode_responses=True)
    
    print("--- Redis Keys ---")
    keys = await redis_client.keys("*")
    print(f"Total Redis keys: {len(keys)}")
    for k in keys[:20]:
        print(f"  {k}")
        
    print("\n--- Suppression Keys in Redis ---")
    suppressions = ["festival:diwali:2026:m_003", "perf:dip:2026:m_002", "perf:spike:2026:m_008", "compliance:dci:radiograph:2026:m_001"]
    for s in suppressions:
        val = await redis_client.get(s) or await redis_client.exists(s)
        print(f"  {s}: {val}")
        
    print("\n--- Wait State Status ---")
    conv_ids = [
        "conv_m_003_studio11_salon_hyderabad_festival_upcoming",
        "conv_m_002_bharat_dentist_mumbai_perf_dip",
        "conv_m_008_zenyoga_gym_chennai_perf_spike",
        "conv_m_001_drmeera_dentist_delhi_compliance_dci_radiograph"
    ]
    for cid in conv_ids:
        wait = await redis_client.get(f"wait:{cid}") or await redis_client.get(cid)
        print(f"  {cid}: {wait}")
        
    print("\n--- MongoDB Contexts Count ---")
    count = await db["contexts"].count_documents({})
    print(f"Contexts count: {count}")
    
    print("\n--- MongoDB Actions Log ---")
    actions = await db["actions"].find({}).to_list(100)
    print(f"Actions logged: {len(actions)}")
    for a in actions[:10]:
        print(f"  {a.get('trigger_id')}: {a.get('conversation_id')} - {a.get('body')[:50]}")

if __name__ == "__main__":
    asyncio.run(main())
