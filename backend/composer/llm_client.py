# backend/composer/llm_client.py
"""
LLMClient: talks to Groq's OpenAI-compatible Chat Completions API.

Why Groq: extremely low latency inference (LPU-backed), which matters a lot
given the hard 30s response budget on /v1/reply and the need to compose up
to TICK_MAX_ACTIONS messages within ~25s on /v1/tick.

Reliability behavior:
- `response_format: {"type": "json_object"}` is requested so the model
  returns valid JSON directly (Groq supports this on supported models).
  We still defensively strip markdown fences in case a model ignores it.
- Retries with exponential backoff on transient errors (timeouts, 429, 5xx).
- Falls back to LLM_FALLBACK_MODEL if the primary model fails on every retry.
- temperature=0 for deterministic output given the same input, per challenge
  requirements.
"""
import asyncio
import json
import logging
from typing import Optional

import httpx

from config import (
    GROQ_API_KEY,
    GROQ_CHAT_ENDPOINT,
    LLM_MODEL,
    LLM_FALLBACK_MODEL,
    LLM_MAX_TOKENS,
    LLM_TEMPERATURE,
    LLM_TIMEOUT_SECONDS,
)
from logging_config import get_logger

logger = get_logger("nexora.llm_client")

RETRYABLE_STATUS_CODES = {408, 409, 425, 429, 500, 502, 503, 504, 529}


class LLMClient:
    def __init__(
        self,
        api_key: str = GROQ_API_KEY,
        endpoint: str = GROQ_CHAT_ENDPOINT,
        model: str = LLM_MODEL,
        fallback_model: str = LLM_FALLBACK_MODEL,
        max_tokens: int = LLM_MAX_TOKENS,
        temperature: float = LLM_TEMPERATURE,
        timeout_seconds: float = LLM_TIMEOUT_SECONDS,
    ):
        self.api_key = api_key
        self.endpoint = endpoint
        self.model = model
        self.fallback_model = fallback_model
        self.max_tokens = max_tokens
        self.temperature = temperature
        self.timeout_seconds = timeout_seconds

    def _headers(self) -> dict:
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

    def _body(self, prompt: dict, model: str, json_mode: bool = True) -> dict:
        body = {
            "model": model,
            "max_tokens": self.max_tokens,
            "temperature": self.temperature,
            "messages": [
                {"role": "system", "content": prompt["system"]},
                {"role": "user", "content": prompt["user"]},
            ],
        }
        if json_mode:
            body["response_format"] = {"type": "json_object"}
        return body

    @staticmethod
    def _extract_json(raw_text: str) -> dict:
        text = raw_text.strip()
        if text.startswith("```"):
            # Strip leading ```json / ``` and trailing ```
            text = text.split("\n", 1)[1] if "\n" in text else text[3:]
            if text.endswith("```"):
                text = text[:-3]
            text = text.strip()
        return json.loads(text)

    async def _call_model(self, prompt: dict, model: str, json_mode: bool = True) -> Optional[dict]:
        if not self.api_key:
            logger.error("GROQ_API_KEY is not set; cannot call LLM")
            return None

        headers = self._headers()
        body = self._body(prompt, model, json_mode=json_mode)

        import time
        t0 = time.perf_counter()
        try:
            async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
                resp = await client.post(self.endpoint, headers=headers, json=body)
                latency = time.perf_counter() - t0
                if resp.status_code in RETRYABLE_STATUS_CODES:
                    logger.warning(
                        "LLM call got retryable status",
                        extra={"ctx": {"status": resp.status_code, "model": model}},
                    )
                    return None
                resp.raise_for_status()
                data = resp.json()
                raw_text = data["choices"][0]["message"]["content"].strip()
                res = self._extract_json(raw_text)
                if isinstance(res, dict):
                    res["_usage"] = data.get("usage", {})
                    res["_latency"] = round(latency, 3)
                return res
        except httpx.TimeoutException:
            logger.warning("LLM call timed out", extra={"ctx": {"model": model}})
            return None
        except httpx.HTTPStatusError as exc:
            logger.error(
                "LLM call failed with non-retryable HTTP error",
                extra={"ctx": {"model": model, "status": exc.response.status_code, "body": exc.response.text[:500]}},
            )
            return None
        except (json.JSONDecodeError, KeyError, IndexError) as exc:
            logger.error(
                "LLM response could not be parsed as JSON",
                extra={"ctx": {"model": model, "error": str(exc)}},
            )
            return None

    async def complete(self, prompt: dict, retries: int = 2) -> Optional[dict]:
        """
        Call Groq with retries + exponential backoff on the primary model,
        then fall back to LLM_FALLBACK_MODEL if every primary attempt fails.
        Returns a parsed JSON dict, or None if every attempt fails.
        """
        for attempt in range(retries + 1):
            result = await self._call_model(prompt, self.model)
            if result is not None:
                return result
            if attempt < retries:
                await asyncio.sleep(2 ** attempt)  # 1s, 2s, ...

        if self.fallback_model and self.fallback_model != self.model:
            logger.info(
                "Primary model failed all retries, trying fallback model",
                extra={"ctx": {"fallback_model": self.fallback_model}},
            )
            result = await self._call_model(prompt, self.fallback_model)
            if result is not None:
                return result

        logger.error("LLM composition failed on primary and fallback models")
        return None
