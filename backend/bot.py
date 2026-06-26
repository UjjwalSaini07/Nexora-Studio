# backend/bot.py
"""
Thin alias for main.py.

challenge-testing-brief.md §7 shows the reference skeleton saved as `bot.py`
and run via `uvicorn bot:app --host 0.0.0.0 --port 8080`. Our actual
implementation lives in main.py (clean module name for the full app), but
this file re-exports the same `app` object so the exact command from the
brief works unmodified, with zero duplicated logic.

Run either of these — they start the identical application:
    uvicorn main:app --host 0.0.0.0 --port 8080
    uvicorn bot:app  --host 0.0.0.0 --port 8080
"""
from main import app  # noqa: F401  (re-exported for `uvicorn bot:app`)
