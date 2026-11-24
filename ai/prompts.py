"""
ai/prompts.py
=============
System prompts and prompt builders for KAI.
All LLM messages flow through here to maintain a consistent identity, tone
and strict JSON/tool-call output format.
"""

from __future__ import annotations

import json
from pathlib import Path

# ---------------------------------------------------------------------------
# Load tools schema once
# ---------------------------------------------------------------------------

_TOOLS_SCHEMA_PATH = Path(__file__).parent.parent / "config" / "tools_schema.json"

def _load_tools_schema() -> str:
    try:
        return json.dumps(json.loads(_TOOLS_SCHEMA_PATH.read_text(encoding="utf-8")), indent=2)
    except Exception:
        return "{}"


TOOLS_SCHEMA_STR = _load_tools_schema()


# ---------------------------------------------------------------------------
# System prompt
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = f"""You are KAI, a friendly, concise and highly capable AI desktop assistant.
You run locally on the user's Windows PC and help with everyday tasks.

## Personality
- Warm, direct and efficient – no filler words, no unnecessary apologies.
- Speak in the same language the user used (Spanish or English).
- Keep replies short unless the user explicitly asks for details.

## Output format (STRICT)
You MUST always respond with a single valid JSON object and NOTHING else.
Do NOT include markdown fences, preamble or prose outside the JSON.

Required schema:
{{
  "tool": "<tool_name>",        // one of the available tools
  "args": {{...}},               // arguments matching the tool's parameter schema
  "speech": "<text to say>"    // short natural-language reply to speak/display (may be "")
}}

## Available tools
{TOOLS_SCHEMA_STR}

## Rules
1. If the user's request maps to a tool, use it. Otherwise use the "answer" tool.
2. Never invent tool names outside the list above.
3. Never include executable code, file deletions or destructive commands.
4. For sensitive actions (move files, open apps) confirm the user's intent once if ambiguous.
5. Dates/times are always relative to the user's local time.
"""


# ---------------------------------------------------------------------------
# Prompt builders
# ---------------------------------------------------------------------------

def build_user_message(text: str, context: dict | None = None) -> str:
    """
    Wrap the user's raw text with optional context metadata.
    *context* can include recent habits, active timers, etc.
    """
    if context:
        ctx_str = "\n".join(f"  {k}: {v}" for k, v in context.items())
        return f"[Context]\n{ctx_str}\n\n[User]\n{text}"
    return text


def build_messages(user_text: str, history: list[dict] | None = None, context: dict | None = None) -> list[dict]:
    """
    Build the full messages list for the LLM.
    *history* is a list of prior {role, content} dicts (oldest first).
    """
    messages: list[dict] = [{"role": "system", "content": SYSTEM_PROMPT}]
    if history:
        # Keep last N turns to avoid exceeding context window
        for turn in history[-6:]:
            messages.append(turn)
    messages.append({"role": "user", "content": build_user_message(user_text, context)})
    return messages
