"""
tests/test_action_dispatcher.py
================================
Unit tests for the action dispatcher and routing logic.
"""

from __future__ import annotations

import pytest

from ai.action_dispatcher import ActionDispatcher, register


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def dispatcher() -> ActionDispatcher:
    return ActionDispatcher()


# ---------------------------------------------------------------------------
# Helper: register a temporary test handler
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _register_test_handler():
    """Register a 'test_echo' tool for use in tests."""
    @register("test_echo")
    async def _echo(args: dict) -> str:
        return f"echo: {args.get('msg', '')}"

    yield

    # Cleanup
    from ai.action_dispatcher import _HANDLERS
    _HANDLERS.pop("test_echo", None)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_dispatch_answer_tool(dispatcher):
    action = {"tool": "answer", "args": {"text": "Hello KAI"}, "speech": "Hello KAI"}
    result = await dispatcher.dispatch(action)
    assert result == "Hello KAI"


@pytest.mark.asyncio
async def test_dispatch_custom_handler(dispatcher):
    action = {"tool": "test_echo", "args": {"msg": "ping"}, "speech": ""}
    result = await dispatcher.dispatch(action)
    assert result == "echo: ping"


@pytest.mark.asyncio
async def test_dispatch_unknown_tool(dispatcher):
    action = {"tool": "nonexistent_tool", "args": {}, "speech": "fallback"}
    result = await dispatcher.dispatch(action)
    # Should fall back to speech or error message, not raise
    assert isinstance(result, str)
    assert len(result) > 0


@pytest.mark.asyncio
async def test_dispatch_empty_tool(dispatcher):
    action = {"tool": "", "args": {}, "speech": "no tool"}
    result = await dispatcher.dispatch(action)
    assert isinstance(result, str)


@pytest.mark.asyncio
async def test_dispatch_handler_raises_value_error(dispatcher):
    @register("bad_tool")
    async def _bad(args):
        raise ValueError("bad input")

    action = {"tool": "bad_tool", "args": {}, "speech": "err"}
    result = await dispatcher.dispatch(action)
    assert "bad input" in result

    from ai.action_dispatcher import _HANDLERS
    _HANDLERS.pop("bad_tool", None)


@pytest.mark.asyncio
async def test_dispatch_handler_raises_permission_error(dispatcher):
    @register("forbidden_tool")
    async def _forbidden(args):
        raise PermissionError("not allowed")

    action = {"tool": "forbidden_tool", "args": {}, "speech": ""}
    result = await dispatcher.dispatch(action)
    assert "blocked" in result.lower() or "not allowed" in result.lower()

    from ai.action_dispatcher import _HANDLERS
    _HANDLERS.pop("forbidden_tool", None)
