# backend/dev_tools/mock_ollama_server.py
"""
DEV-ONLY TOOL — not part of the production deliverable.

A minimal FastAPI app that mimics Ollama's /api/generate endpoint shape,
used only so the OFFICIAL, UNMODIFIED judge_simulator.py (which supports
LLM_PROVIDER="ollama" pointed at a local OLLAMA_URL) can run end-to-end in
this sandbox, where no real LLM provider is reachable.

This lets us exercise the real judge_simulator.py's scoring/parsing logic
against our real bot's real responses, without editing magicpin's reference
file at all. The "judge" scores produced this way are NOT meaningful
(this mock returns a generic plausible-looking JSON score every time) —
they only prove the wiring (bot <-> simulator <-> "LLM") works end-to-end.
Real scoring requires the user's own LLM API key, exactly as the brief
describes.

Run (from backend/ directory):
    uvicorn dev_tools.mock_ollama_server:app --host 0.0.0.0 --port 11434
"""
import json
import time

from fastapi import FastAPI, Request

app = FastAPI()


@app.post("/api/generate")
async def generate(request: Request):
    body = await request.json()
    prompt = body.get("prompt", "")

    # The judge_simulator.py LLMScorer prompt asks for a JSON object with
    # specific scoring keys. Detect that shape and return a plausible,
    # generically "decent" score so the simulator's JSON parsing path is
    # exercised for real, without claiming this represents real judgment.
    if '"specificity"' in prompt or "specificity_reason" in prompt or "Score this" in prompt:
        response_text = json.dumps({
            "specificity": 7, "specificity_reason": "Mock judge: message references concrete context fields.",
            "category_fit": 7, "category_fit_reason": "Mock judge: tone roughly matches category voice.",
            "merchant_fit": 7, "merchant_fit_reason": "Mock judge: references merchant-specific details.",
            "decision_quality": 7, "decision_quality_reason": "Mock judge: trigger reasoning is present.",
            "engagement_compulsion": 6, "engagement_reason": "Mock judge: has a single clear CTA.",
            "hint": "This is a MOCK score from a local test double, not a real LLM judgment.",
        })
    else:
        # Generic "are you there" connectivity check the simulator does at startup.
        response_text = "ready"

    return {
        "model": body.get("model", "mock-llama3"),
        "created_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "response": response_text,
        "done": True,
    }
