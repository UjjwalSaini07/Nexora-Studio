import json
import os
from pathlib import Path
from datetime import datetime, timezone

from logging_config import get_logger

logger = get_logger("nexora.dataset_loader")

BACKEND_DIR = Path(__file__).parent.parent  # backend/
REPO_ROOT = BACKEND_DIR.parent              # nexora-bot/


def _resolve_dataset_dir() -> Path:
    env_dir = os.getenv("EXPANDED_DATASET_DIR")
    if env_dir:
        return Path(env_dir)

    expanded_dir = REPO_ROOT / "expanded"
    if expanded_dir.exists() and any(expanded_dir.rglob("*.json")):
        return expanded_dir

    seed_dir = REPO_ROOT / "dataset"
    return seed_dir


async def _load_scope(mongo, redis, scope: str, dir_path: Path, id_field: str):
    if not dir_path.exists():
        logger.info(f"No directory for scope={scope} at {dir_path}, skipping.")
        return 0

    now = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    loaded = 0
    for f in sorted(dir_path.glob("*.json")):
        try:
            data = json.loads(f.read_text(encoding="utf-8-sig"))
        except json.JSONDecodeError as exc:
            logger.error(f"Failed to parse {f}: {exc}")
            continue

        context_id = data.get(id_field, f.stem)
        existing = await mongo.get_context(scope, context_id)
        if existing:
            # Re-sync context version to Redis if missing from cache
            await redis.set_context_version_if_new(scope, context_id, existing.get("version", 1))
            continue

        await mongo.upsert_context(scope, context_id, 1, data, now)
        await redis.set_context_version_if_new(scope, context_id, 1)
        loaded += 1

    return loaded


async def load_dataset_to_mongo(mongo, redis):
    """Load all dataset files into MongoDB and update the Redis version index."""
    base_dir = _resolve_dataset_dir()
    logger.info(f"Loading dataset from {base_dir}")

    counts = {
        "category": await _load_scope(mongo, redis, "category", base_dir / "categories", "slug"),
        "merchant": await _load_scope(mongo, redis, "merchant", base_dir / "merchants", "merchant_id"),
        "customer": await _load_scope(mongo, redis, "customer", base_dir / "customers", "customer_id"),
        "trigger": await _load_scope(mongo, redis, "trigger", base_dir / "triggers", "id"),
    }

    total = sum(counts.values())
    logger.info(f"Dataset loaded at startup: {counts} (total new={total})")
    return counts
