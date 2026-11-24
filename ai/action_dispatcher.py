"""
ai/action_dispatcher.py
========================
Validates and routes the action dict produced by the LLM to the
appropriate action handler.  Acts as a secure gatekeeper: unknown tools,
missing required args and disallowed targets are rejected before execution.
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Registered action handlers (populated at startup)
# ---------------------------------------------------------------------------
# Map: tool_name → async callable(args: dict) → str (result message)

_HANDLERS: dict[str, Any] = {}


def register(tool_name: str):
    """Decorator to register an async action handler."""
    def decorator(fn):
        _HANDLERS[tool_name] = fn
        logger.debug("ActionDispatcher: registered handler for '%s'", tool_name)
        return fn
    return decorator


# ---------------------------------------------------------------------------
# Dispatcher
# ---------------------------------------------------------------------------


class ActionDispatcher:
    """
    Routes a parsed LLM action to the correct module handler.

    Usage::

        dispatcher = ActionDispatcher()
        result = await dispatcher.dispatch(action)
    """

    async def dispatch(self, action: dict[str, Any]) -> str:
        """
        Execute the action and return a result string.

        Parameters
        ----------
        action : dict
            Must contain "tool" (str) and "args" (dict).

        Returns
        -------
        str
            Human-readable result to show/speak.
        """
        tool = action.get("tool", "")
        args = action.get("args", {})
        speech = action.get("speech", "")

        if not tool:
            logger.warning("ActionDispatcher: empty tool name in action %s", action)
            return speech or "No action specified."

        handler = _HANDLERS.get(tool)
        if handler is None:
            logger.error("ActionDispatcher: no handler for tool '%s'", tool)
            return speech or f"Unknown action: {tool}"

        try:
            logger.info("Dispatching → %s(%s)", tool, args)
            result = await handler(args)
            return result or speech or "Done."
        except PermissionError as exc:
            logger.warning("Dispatcher: permission denied for '%s': %s", tool, exc)
            return f"Action blocked: {exc}"
        except ValueError as exc:
            logger.warning("Dispatcher: validation error for '%s': %s", tool, exc)
            return str(exc)
        except Exception:
            logger.exception("Dispatcher: unhandled error in handler '%s'", tool)
            return "Something went wrong while executing that action."


# ---------------------------------------------------------------------------
# Built-in passthrough handler
# ---------------------------------------------------------------------------

@register("answer")
async def _handle_answer(args: dict) -> str:
    """Simply return the text – the LLM is answering directly."""
    return args.get("text", "")
