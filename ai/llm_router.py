"""
ai/llm_router.py
================
Hybrid LLM Router for Troko-Desk.
Local-first strategy:
  1. If llama-cpp-python is available and GGUF is ready → local direct inference.
  2. Otherwise fallback to local Ollama (llama3.2:3b).
  3. If local unavailable and hybrid mode enabled with API key → online fallback.
  4. Always returns clean structured JSON tool action dicts.
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any, Optional

from config.settings import settings

logger = logging.getLogger(__name__)

_JSON_RE = re.compile(r"\{.*\}", re.DOTALL)


def _extract_json(raw: str) -> dict[str, Any]:
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

    raise ValueError(f"Could not extract JSON from LLM output:\n{raw[:250]}")


def _safe_action(speech: str = "Disculpa, no logré procesar esa respuesta.") -> dict[str, Any]:
    return {"tool": "answer", "args": {"text": speech}, "speech": speech}


class LLMRouter:
    def __init__(self) -> None:
        self._llama_cpp_model = None
        self._init_llama_cpp()

    def _init_llama_cpp(self) -> None:
        """Attempt to load local Llama GGUF if llama-cpp-python is installed and model exists."""
        from pathlib import Path
        model_file = Path(settings.llama_model_path)
        if model_file.exists() and model_file.stat().st_size > 100 * 1024 * 1024:
            try:
                from llama_cpp import Llama
                logger.info("Initializing local llama.cpp model from %s...", model_file)
                self._llama_cpp_model = Llama(
                    model_path=str(model_file),
                    n_ctx=2048,
                    n_threads=4,
                    verbose=False,
                )
                logger.info("Local llama.cpp model loaded successfully.")
            except ImportError:
                logger.debug("llama-cpp-python not installed; using Ollama as local engine.")
            except Exception as exc:
                logger.warning("Could not initialize llama-cpp-python: %s", exc)

    async def chat(self, messages: list[dict]) -> dict[str, Any]:
        mode = settings.llm_mode.lower()

        # 1. Local execution
        if mode in ("local", "hybrid"):
            # A) Try local llama-cpp if active
            if self._llama_cpp_model is not None:
                try:
                    raw = self._call_llama_cpp(messages)
                    return _extract_json(raw)
                except Exception as exc:
                    logger.warning("Local llama.cpp inference failed: %s", exc)

            # B) Try Ollama local
            try:
                raw = await self._call_ollama(messages)
                return _extract_json(raw)
            except Exception as exc:
                logger.warning("Local Ollama call failed: %s", exc)

            # C) Hybrid online fallback
            if mode == "hybrid" and settings.openai_api_key:
                logger.info("Switching to online hybrid fallback...")
                try:
                    raw = await self._call_openai(messages)
                    return _extract_json(raw)
                except Exception as exc2:
                    logger.error("Hybrid fallback also failed: %s", exc2)

            return _safe_action(
                "No pude conectar con el modelo local de Troko. "
                "Asegúrate de tener Ollama o el modelo Llama 3.2 descargado."
            )

        # 2. Pure online mode
        if mode == "online":
            if not settings.openai_api_key:
                return _safe_action("Clave de API online no configurada en .env.")
            try:
                raw = await self._call_openai(messages)
                return _extract_json(raw)
            except Exception as exc:
                logger.error("Online LLM call failed: %s", exc)
                return _safe_action()

        return _safe_action("Modo de LLM no reconocido.")

    def _call_llama_cpp(self, messages: list[dict]) -> str:
        prompt = ""
        for m in messages:
            role = m.get("role", "user")
            content = m.get("content", "")
            prompt += f"<|im_start|>{role}\n{content}<|im_end|>\n"
        prompt += "<|im_start|>assistant\n"

        output = self._llama_cpp_model(
            prompt,
            max_tokens=400,
            temperature=0.2,
            stop=["<|im_end|>"],
        )
        return output["choices"][0]["text"].strip()

    async def _call_ollama(self, messages: list[dict]) -> str:
        import httpx

        payload = {
            "model": settings.ollama_model,
            "messages": messages,
            "stream": False,
            "format": "json",
            "options": {"temperature": 0.25, "num_predict": 450},
        }
        url = f"{settings.ollama_base_url}/api/chat"
        async with httpx.AsyncClient(timeout=45.0) as client:
            resp = await client.post(url, json=payload)
            resp.raise_for_status()
            data = resp.json()

        content = data["message"]["content"]
        logger.debug("Ollama response: %s", content[:150])
        return content

    async def _call_openai(self, messages: list[dict]) -> str:
        import httpx

        headers = {
            "Authorization": f"Bearer {settings.openai_api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": settings.openai_model,
            "messages": messages,
            "temperature": 0.2,
            "max_tokens": 450,
            "response_format": {"type": "json_object"},
        }
        url = f"{settings.openai_base_url}/chat/completions"
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(url, json=payload, headers=headers)
            resp.raise_for_status()
            data = resp.json()

        content = data["choices"][0]["message"]["content"]
        return content
