# backend/storage/mongo_store.py
"""
MongoStore: durable persistence for full context payloads and the
actions/conversation audit trail. Redis is the hot path (versions,
suppression, live conversation state); Mongo is the system of record.
"""
from datetime import datetime, timezone
from typing import Optional

import motor.motor_asyncio
from pymongo import ASCENDING, DESCENDING
from pymongo.errors import PyMongoError

from config import MONGO_URI, MONGO_DB
from logging_config import get_logger

logger = get_logger("nexora.mongo_store")


class MongoStore:
    def __init__(self, uri: str = MONGO_URI, db_name: str = MONGO_DB):
        self.client = motor.motor_asyncio.AsyncIOMotorClient(uri, serverSelectionTimeoutMS=5000)
        self.db = self.client[db_name]
        self.contexts = self.db["contexts"]
        self.conversations = self.db["conversations"]
        self.actions_log = self.db["actions_log"]
        self.replies_log = self.db["replies_log"]
        self.ticks_log = self.db["ticks_log"]
        self.suppressions_log = self.db["suppressions_log"]
        self.contexts_history = self.db["contexts_history"]

    async def ping(self) -> bool:
        try:
            await self.client.admin.command("ping")
            return True
        except PyMongoError as exc:
            logger.error("Mongo ping failed", extra={"ctx": {"error": str(exc)}})
            return False

    async def ensure_indexes(self):
        """Create indexes idempotently. Safe to call on every startup."""
        await self.contexts.create_index(
            [("scope", ASCENDING), ("context_id", ASCENDING)], unique=True, name="scope_context_id_unique"
        )
        await self.actions_log.create_index([("logged_at", DESCENDING)], name="logged_at_desc")
        await self.actions_log.create_index([("merchant_id", ASCENDING)], name="merchant_id_idx")
        await self.actions_log.create_index([("trigger_id", ASCENDING)], name="trigger_id_idx")
        await self.replies_log.create_index([("logged_at", DESCENDING)], name="replies_logged_at_desc")
        await self.replies_log.create_index([("conversation_id", ASCENDING)], name="replies_conv_id_idx")
        await self.ticks_log.create_index([("created_at", DESCENDING)], name="ticks_created_at_desc")
        await self.suppressions_log.create_index([("suppression_key", ASCENDING)], unique=True, name="suppression_key_unique")
        await self.contexts_history.create_index([("scope", ASCENDING), ("context_id", ASCENDING), ("version", DESCENDING)], name="history_scope_id_version")
        logger.info("Mongo indexes ensured")

    def close(self):
        self.client.close()

    async def upsert_context(self, scope: str, context_id: str,
                              version: int, payload: dict, delivered_at: str):
        stored_at_str = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        await self.contexts.replace_one(
            {"scope": scope, "context_id": context_id},
            {
                "scope": scope,
                "context_id": context_id,
                "version": version,
                "payload": payload,
                "delivered_at": delivered_at,
                "stored_at": stored_at_str,
            },
            upsert=True
        )
        # Log this specific version payload to history
        await self.contexts_history.replace_one(
            {"scope": scope, "context_id": context_id, "version": version},
            {
                "scope": scope,
                "context_id": context_id,
                "version": version,
                "payload": payload,
                "delivered_at": delivered_at,
                "stored_at": stored_at_str,
            },
            upsert=True
        )

    async def get_context(self, scope: str, context_id: str) -> Optional[dict]:
        doc = await self.contexts.find_one(
            {"scope": scope, "context_id": context_id},
            {"_id": 0}
        )
        return doc

    async def list_contexts(self, scope: Optional[str] = None, limit: int = 200) -> list[dict]:
        query = {"scope": scope} if scope else {}
        cursor = self.contexts.find(query, {"_id": 0}).limit(limit)
        return await cursor.to_list(length=limit)

    async def count_contexts(self, scope: str) -> int:
        return await self.contexts.count_documents({"scope": scope})

    async def log_action(self, action: dict):
        doc = dict(action)
        doc["logged_at"] = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        await self.actions_log.insert_one(doc)

    async def get_recent_actions(self, limit: int = 50) -> list:
        cursor = self.actions_log.find(
            {}, {"_id": 0}
        ).sort("logged_at", -1).limit(limit)
        return await cursor.to_list(length=limit)

    async def log_reply(self, reply_record: dict):
        doc = dict(reply_record)
        doc["logged_at"] = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        await self.replies_log.insert_one(doc)

    async def get_recent_replies(self, limit: int = 50) -> list:
        cursor = self.replies_log.find(
            {}, {"_id": 0}
        ).sort("logged_at", -1).limit(limit)
        return await cursor.to_list(length=limit)

    async def get_replies_for_conversation(self, conversation_id: str, limit: int = 100) -> list:
        cursor = self.replies_log.find(
            {"conversation_id": conversation_id}, {"_id": 0}
        ).sort("logged_at", 1).limit(limit)
        return await cursor.to_list(length=limit)

    async def log_tick(self, tick_record: dict):
        doc = dict(tick_record)
        doc["created_at"] = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        await self.ticks_log.insert_one(doc)

    async def get_recent_ticks(self, limit: int = 50) -> list:
        cursor = self.ticks_log.find(
            {}, {"_id": 0}
        ).sort("created_at", -1).limit(limit)
        return await cursor.to_list(length=limit)

    async def log_suppression(self, suppression_key: str):
        await self.suppressions_log.replace_one(
            {"suppression_key": suppression_key},
            {
                "suppression_key": suppression_key,
                "set_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            },
            upsert=True
        )

    async def remove_suppression(self, suppression_key: str):
        await self.suppressions_log.delete_one({"suppression_key": suppression_key})

    async def get_all_suppressions(self) -> list[str]:
        cursor = self.suppressions_log.find({}, {"_id": 0, "suppression_key": 1})
        docs = await cursor.to_list(length=5000)
        return [d["suppression_key"] for d in docs if "suppression_key" in d]

    async def get_context_history(self, scope: str, context_id: str) -> list:
        cursor = self.contexts_history.find(
            {"scope": scope, "context_id": context_id},
            {"_id": 0}
        ).sort("version", -1)
        return await cursor.to_list(length=100)

    async def wipe_all(self) -> dict:
        """
        Drops all NEXORA collections. Used by the optional POST /v1/teardown
        endpoint per challenge-testing-brief.md §11: bots must not persist
        context data after the test ends.
        """
        counts = {}
        for name, collection in [
            ("contexts", self.contexts),
            ("conversations", self.conversations),
            ("actions_log", self.actions_log),
            ("replies_log", self.replies_log),
            ("ticks_log", self.ticks_log),
            ("suppressions_log", self.suppressions_log),
            ("contexts_history", self.contexts_history),
        ]:
            result = await collection.delete_many({})
            counts[name] = result.deleted_count
        return counts
