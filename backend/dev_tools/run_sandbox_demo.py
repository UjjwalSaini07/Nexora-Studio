"""
DEV-ONLY TOOL — not part of the production deliverable.

Used to smoke-test the real FastAPI app end-to-end in environments where a
real MongoDB server isn't installable (e.g. a locked-down sandbox with no
apt package and no network access to MongoDB's own repo). It boots the
actual `backend/main.py` app against a REAL Redis (install via apt/brew/etc.
in dev) and an in-memory Mongo double (mongomock-motor) that satisfies the
exact same interface as the real `MongoStore`.

This proves the HTTP server boots, serves /v1/healthz, /v1/metadata,
/v1/context, /v1/tick, and /v1/reply correctly over real network sockets —
the parts of the stack that ASGITransport-based pytest integration tests
don't exercise (actual TCP binding, uvicorn's request handling, real
startup-lifespan timing).

For real local development with actual MongoDB + Redis, just run:
    uvicorn main:app --host 0.0.0.0 --port 8080
directly from the backend/ directory instead of this script.

Run (from backend/ directory):
    python3 dev_tools/run_sandbox_demo.py
"""
import sys
from pathlib import Path

# backend/ itself must be on sys.path (this file lives in backend/dev_tools/)
sys.path.insert(0, str(Path(__file__).parent.parent))

import mongomock_motor
import uvicorn

import main as main_module
from storage.mongo_store import MongoStore


class SandboxMongoStore(MongoStore):
    def __init__(self, *_args, **_kwargs):
        self.client = mongomock_motor.AsyncMongoMockClient()
        self.db = self.client["nexora_bot_sandbox"]
        self.contexts = self.db["contexts"]
        self.conversations = self.db["conversations"]
        self.actions_log = self.db["actions_log"]
        self.replies_log = self.db["replies_log"]

    async def ping(self) -> bool:
        return True

    async def ensure_indexes(self):
        return None


# Monkeypatch: main.py's lifespan constructs MongoStore() directly. For this
# sandbox-only smoke test we swap it for the in-memory double before the app
# starts, since a real mongod binary isn't installable in this environment.
main_module.MongoStore = SandboxMongoStore

if __name__ == "__main__":
    uvicorn.run(main_module.app, host="0.0.0.0", port=8080, log_level="info")
