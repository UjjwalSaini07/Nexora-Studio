"""
ContextAssembler: given a TriggerContext, resolves and validates the other
3 contexts the composer needs (category, merchant, customer-if-applicable).

Returns None (logged, not raised) if anything required is missing — a
missing-context trigger must never crash /v1/tick; it should simply be
skipped for this tick and retried on a future one once the context arrives.
"""
from typing import Optional, Tuple

from models.context import CategoryContext, MerchantContext, CustomerContext, TriggerContext
from storage.redis_store import RedisStore
from storage.mongo_store import MongoStore
from logging_config import get_logger

logger = get_logger("nexora.context_assembler")


class ContextAssembler:
    def __init__(self, redis: RedisStore, mongo: MongoStore):
        self.redis = redis
        self.mongo = mongo

    async def assemble(
        self, trigger: TriggerContext
    ) -> Optional[Tuple[CategoryContext, MerchantContext, Optional[CustomerContext]]]:
        # 1. Merchant is always required (every trigger is ultimately scoped
        #    to a merchant, even customer-scoped ones which act on a
        #    merchant's behalf).
        if not trigger.merchant_id:
            logger.warning(
                "Trigger missing merchant_id, cannot assemble",
                extra={"ctx": {"trigger_id": trigger.id}},
            )
            return None

        merchant_doc = await self.mongo.get_context("merchant", trigger.merchant_id)
        if not merchant_doc:
            logger.warning(
                "Merchant context not yet loaded for trigger",
                extra={"ctx": {"trigger_id": trigger.id, "merchant_id": trigger.merchant_id}},
            )
            return None

        try:
            merchant = MerchantContext(**merchant_doc["payload"])
        except Exception as exc:
            logger.error(
                "Merchant context failed validation",
                extra={"ctx": {"merchant_id": trigger.merchant_id, "error": str(exc)}},
            )
            return None

        # 2. Category, keyed by merchant.category_slug
        category_doc = await self.mongo.get_context("category", merchant.category_slug)
        if not category_doc:
            logger.warning(
                "Category context not yet loaded",
                extra={"ctx": {"trigger_id": trigger.id, "category_slug": merchant.category_slug}},
            )
            return None

        try:
            category = CategoryContext(**category_doc["payload"])
        except Exception as exc:
            logger.error(
                "Category context failed validation",
                extra={"ctx": {"category_slug": merchant.category_slug, "error": str(exc)}},
            )
            return None

        # 3. Customer, only if the trigger is customer-scoped
        customer: Optional[CustomerContext] = None
        if trigger.scope == "customer":
            if not trigger.customer_id:
                logger.warning(
                    "Customer-scoped trigger missing customer_id",
                    extra={"ctx": {"trigger_id": trigger.id}},
                )
                return None
            customer_doc = await self.mongo.get_context("customer", trigger.customer_id)
            if not customer_doc:
                logger.warning(
                    "Customer context not yet loaded for customer-scoped trigger",
                    extra={"ctx": {"trigger_id": trigger.id, "customer_id": trigger.customer_id}},
                )
                return None
            try:
                customer = CustomerContext(**customer_doc["payload"])
            except Exception as exc:
                logger.error(
                    "Customer context failed validation",
                    extra={"ctx": {"customer_id": trigger.customer_id, "error": str(exc)}},
                )
                return None

        return category, merchant, customer
