from fastapi import APIRouter, Depends
from dependencies import get_redis, get_mongo, verify_auth
from storage.redis_store import RedisStore
from storage.mongo_store import MongoStore

router = APIRouter()


@router.post("/v1/demo/reset", dependencies=[Depends(verify_auth)])
async def reset_demo(
    redis: RedisStore = Depends(get_redis),
    mongo: MongoStore = Depends(get_mongo),
):
    # Wipe Redis demo keys
    redis_results = await redis.wipe_demo_keys()
    
    # Wipe MongoDB suppressions
    mongo_suppressions_count = await mongo.wipe_demo_suppressions()
    
    return {
        "success": True,
        "suppression_keys_removed": redis_results.get("suppression_keys_removed", 0),
        "wait_states_removed": redis_results.get("wait_states_removed", 0),
        "conversation_states_removed": redis_results.get("conversation_states_removed", 0),
        "message": "Demo state reset successfully."
    }
