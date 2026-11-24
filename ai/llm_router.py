"""
ai/llm_router.py
================
Hybrid LLM router: local-first (Ollama) with optional online fallback.

Strategy:
  1. If llm_mode == "local" or "hybrid"  → try Ollama first.
  2. If Ollama fails and llm_mode == "hybrid" and openai_api_key is set
     → fall back to OpenAI-compatible endpoint.
  3. If llm_mode == "online"             → use online provider directly.

Always returns a parsed action dict (tool + args + speech).
Malformed JSON responses are caught and wrapped in a safe fallback.
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Safe JSON extractor
# ---------------------------------------------------------------------------

_JSON_RE = re.compile(r"\{.*\}", re.DOTALL)


def _extract_json(raw: str) -> dict[str, Any]:
    """
    Try to parse *raw* as JSON.  If the model added prose around the JSON
    block, extract the first {...} and parse that.
    Raises ValueError if extraction fails.
    """
    raw = raw.strip()
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        pass

    match = _JSON_RE.search(raw)
    if match:
        try:
            return json.loads(match.group())
        except json.JSONDecodeError:
            pass

    raise ValueError(f"Could not extract JSON from model output:\n{raw[:300]}")


def _safe_action(text: str = "Sorry, I didn't understand that.") -> dict[str, Any]:
    return {"tool": "answer", "args": {"text": text}, "speech": text}


# ---------------------------------------------------------------------------
# LLMRouter
# ---------------------------------------------------------------------------


class LLMRouter:
    """
    Routes LLM calls through the configured provider chain.

    Usage::

        router = LLMRouter()
        action = await router.chat(messages)
        # action == {"tool": "answer", "args": {"text": "..."}, "speech": "..."}
    """

    def __init__(self) -> None:
        from config.settings import settings
        self._settings = settings

    # ------------------------------------------------------------------
    # Public async entry point
    # ------------------------------------------------------------------

    async def chat(self, messages: list[dict]) -> dict[str, Any]:
        """
        Send *messages* to the LLM and return a parsed action dict.
        """
        mode = self._settings.llm_mode.lower()

        if mode in ("local", "hybrid"):
            try:
                raw = await self._call_ollama(messages)
                return _extract_json(raw)
            except Exception as exc:
                logger.warning("Ollama failed: %s", exc)
                if mode == "hybrid" and self._settings.openai_api_key:
                    logger.info("Falling back to online provider…")
                    try:
                        raw = await self._call_openai(messages)
                        return _extract_json(raw)
                    except Exception as exc2:
                        logger.error("Online fallback also failed: %s", exc2)
                        return _safe_action()
                return _safe_action(
                    "No estoy conectado a ningún modelo de IA. "
                    "Por favor asegúrate de que Ollama esté corriendo."
                )

        if mode == "online":
            if not self._settings.openai_api_key:
                return _safe_action("API key not configured for online mode.")
            try:
                raw = await self._call_openai(messages)
                return _extract_json(raw)
            except Exception as exc:
                logger.error("Online provider failed: %s", exc)
                return _safe_action()

        return _safe_action(f"Unknown LLM mode: {mode}")

    # ------------------------------------------------------------------
    # Ollama (local)
    # ------------------------------------------------------------------

    async def _call_ollama(self, messages: list[dict]) -> str:
        import httpx

        payload = {
            "model": self._settings.ollama_model,
            "messages": messages,
            "stream": False,
            "format": "json",
            "options": {
                "temperature": 0.3,
                "num_predict": 512,
            },
        }
        url = f"{self._settings.ollama_base_url}/api/chat"

        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.post(url, json=payload)
            resp.raise_for_status()
            data = resp.json()

        content: str = data["message"]["content"]
        logger.debug("Ollama raw response: %s", content[:200])
        return content

    # ------------------------------------------------------------------
    # OpenAI-compatible endpoint (online fallback)
    # ------------------------------------------------------------------

    async def _call_openai(self, messages: list[dict]) -> str:
        import httpx

        headers = {
            "Authorization": f"Bearer {self._settings.openai_api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": self._settings.openai_model,
            "messages": messages,
            "temperature": 0.3,
            "max_tokens": 512,
            "response_format": {"type": "json_object"},
        }
        url = f"{self._settings.openai_base_url}/chat/completions"

        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(url, json=payload, headers=headers)
            resp.raise_for_status()
            data = resp.json()

        content: str = data["choices"][0]["message"]["content"]
        logger.debug("OpenAI raw response: %s", content[:200])
        return content
