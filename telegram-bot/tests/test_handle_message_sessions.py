import asyncio
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import bot  # noqa: E402
from agent_runner import AgentResult  # noqa: E402


class FakeSessionManager:
    def __init__(self):
        self.asks = []
        self.stops = []
        self.created = []

    def get_or_create(self, chat_id, mode="implicit"):
        # Sync, like the real SessionManager.get_or_create. Bare /chat uses this
        # to open a session without sending a prompt to Claude.
        self.created.append((chat_id, mode))
        return None, "created"

    async def ask(self, chat_id, prompt, mode="implicit"):
        self.asks.append((chat_id, prompt, mode))
        return AgentResult(reply=f"session: {prompt}"), "created"

    async def stop(self, chat_id):
        self.stops.append(chat_id)
        return True


def _update_context(chat_id, text):
    update = MagicMock()
    update.effective_chat.id = chat_id
    update.message.text = text
    update.message.reply_text = AsyncMock()
    context = MagicMock()
    context.bot.send_chat_action = AsyncMock()
    return update, context


def test_normal_text_uses_implicit_session(monkeypatch):
    monkeypatch.setattr(bot, "ALLOWED_CHAT_ID", 111)
    manager = FakeSessionManager()
    monkeypatch.setattr(bot, "SESSION_MANAGER", manager)
    update, context = _update_context(111, "hello")

    asyncio.run(bot.handle_message(update, context))

    assert manager.asks == [(111, "hello", "implicit")]
    update.message.reply_text.assert_awaited_once_with("session: hello")


def test_chat_text_uses_chat_session(monkeypatch):
    monkeypatch.setattr(bot, "ALLOWED_CHAT_ID", 111)
    manager = FakeSessionManager()
    monkeypatch.setattr(bot, "SESSION_MANAGER", manager)
    update, context = _update_context(111, "/chat help me")

    asyncio.run(bot.handle_message(update, context))

    assert manager.asks == [(111, "help me", "chat")]


def test_chat_without_text_confirms(monkeypatch):
    monkeypatch.setattr(bot, "ALLOWED_CHAT_ID", 111)
    manager = FakeSessionManager()
    monkeypatch.setattr(bot, "SESSION_MANAGER", manager)
    update, context = _update_context(111, "/chat")

    asyncio.run(bot.handle_message(update, context))

    assert manager.asks == []
    assert manager.created == [(111, "chat")]
    update.message.reply_text.assert_awaited_once_with("Chat mode started.")


def test_stop_closes_session(monkeypatch):
    monkeypatch.setattr(bot, "ALLOWED_CHAT_ID", 111)
    manager = FakeSessionManager()
    monkeypatch.setattr(bot, "SESSION_MANAGER", manager)
    update, context = _update_context(111, "/stop")

    asyncio.run(bot.handle_message(update, context))

    assert manager.stops == [111]
    update.message.reply_text.assert_awaited_once_with("Conversation stopped.")


def test_command_plus_conversation_runs_command_then_session(monkeypatch):
    monkeypatch.setattr(bot, "ALLOWED_CHAT_ID", 111)
    manager = FakeSessionManager()
    monkeypatch.setattr(bot, "SESSION_MANAGER", manager)
    monkeypatch.setattr(bot, "run_agent", AsyncMock(return_value=AgentResult(reply="today result")))
    update, context = _update_context(111, "/today help me prioritize")

    asyncio.run(bot.handle_message(update, context))

    assert bot.run_agent.await_args.args == ("/today",)
    assert "today result" in manager.asks[0][1]
    assert "help me prioritize" in manager.asks[0][1]
    assert manager.asks[0][2] == "implicit"


def test_bare_add_runs_lifeos_only_one_shot(monkeypatch):
    """/add is the deterministic skill lane: lifeos-only one-shot, no session."""
    monkeypatch.setattr(bot, "ALLOWED_CHAT_ID", 111)
    manager = FakeSessionManager()
    monkeypatch.setattr(bot, "SESSION_MANAGER", manager)
    monkeypatch.setattr(bot, "run_agent", AsyncMock(return_value=AgentResult(reply="added")))
    update, context = _update_context(111, "/add")

    asyncio.run(bot.handle_message(update, context))

    assert bot.run_agent.await_args.args == ("/add",)
    assert bot.run_agent.await_args.kwargs.get("lifeos_only") is True
    assert manager.asks == []  # must not touch the shared session
    update.message.reply_text.assert_awaited_once_with("added")


def test_add_with_details_runs_lifeos_only_one_shot(monkeypatch):
    """"/add <details>" also stays in the skill lane instead of the shared session."""
    monkeypatch.setattr(bot, "ALLOWED_CHAT_ID", 111)
    manager = FakeSessionManager()
    monkeypatch.setattr(bot, "SESSION_MANAGER", manager)
    monkeypatch.setattr(bot, "run_agent", AsyncMock(return_value=_created_add_result()))
    update, context = _update_context(111, "/add buy detergent for laundromat")

    asyncio.run(bot.handle_message(update, context))

    # Full text (command + details) is passed so the skill sees the request.
    assert bot.run_agent.await_args.args == ("/add buy detergent for laundromat",)
    assert bot.run_agent.await_args.kwargs.get("lifeos_only") is True
    assert manager.asks == []


# --- pending /add continuation ---------------------------------------------
def _held_add_result(reply="What's the due date?"):
    """An /add run that asked for a missing field (created:false)."""
    return AgentResult(reply=reply, tool_results=[{
        "name": "mcp__lifeos__add_record", "is_error": False,
        "content": '{"created": false, "error": "missing_required", "fields": ["due_date"]}'}])


def _created_add_result(reply="Added."):
    """An /add run that actually created the record (created:true)."""
    return AgentResult(reply=reply, tool_results=[{
        "name": "mcp__lifeos__add_record", "is_error": False,
        "content": '{"created": true, "id": "abc", "url": "http://n"}'}])


def test_incomplete_add_holds_pending(monkeypatch):
    """An /add missing a field is remembered so the next reply can finish it."""
    monkeypatch.setattr(bot, "ALLOWED_CHAT_ID", 111)
    monkeypatch.setattr(bot, "PENDING_ADDS", {})
    monkeypatch.setattr(bot, "SESSION_MANAGER", FakeSessionManager())
    monkeypatch.setattr(bot, "run_agent", AsyncMock(return_value=_held_add_result()))
    update, context = _update_context(111, "/add call abrahim for evening dresses")

    asyncio.run(bot.handle_message(update, context))

    assert 111 in bot.PENDING_ADDS
    assert bot.PENDING_ADDS[111]["text"] == "/add call abrahim for evening dresses"


def test_completed_add_leaves_no_pending(monkeypatch):
    monkeypatch.setattr(bot, "ALLOWED_CHAT_ID", 111)
    monkeypatch.setattr(bot, "PENDING_ADDS", {})
    monkeypatch.setattr(bot, "SESSION_MANAGER", FakeSessionManager())
    monkeypatch.setattr(bot, "run_agent", AsyncMock(return_value=_created_add_result()))
    update, context = _update_context(111, "/add call abrahim tomorrow at 10")

    asyncio.run(bot.handle_message(update, context))

    assert 111 not in bot.PENDING_ADDS


def test_plain_reply_completes_pending_add(monkeypatch):
    """A plain-text reply to a held /add re-runs a lifeos-only add, not a session."""
    monkeypatch.setattr(bot, "ALLOWED_CHAT_ID", 111)
    monkeypatch.setattr(bot, "PENDING_ADDS", {})
    manager = FakeSessionManager()
    monkeypatch.setattr(bot, "SESSION_MANAGER", manager)
    calls = AsyncMock(side_effect=[_held_add_result(), _created_add_result("Added ✅")])
    monkeypatch.setattr(bot, "run_agent", calls)

    # 1) held /add
    u1, c1 = _update_context(111, "/add call abrahim for evening dresses")
    asyncio.run(bot.handle_message(u1, c1))
    assert 111 in bot.PENDING_ADDS

    # 2) plain reply with the missing date
    u2, c2 = _update_context(111, "Tomorrow at 10")
    asyncio.run(bot.handle_message(u2, c2))

    # the follow-up ran a lifeos-only add carrying BOTH the request and the reply,
    # and never went to the shared session.
    combined = calls.await_args.args[0]
    assert "call abrahim" in combined
    assert "Tomorrow at 10" in combined
    assert calls.await_args.kwargs.get("lifeos_only") is True
    assert manager.asks == []
    assert 111 not in bot.PENDING_ADDS  # cleared on completion
    u2.message.reply_text.assert_awaited_once_with("Added ✅")


def test_plain_reply_without_pending_uses_session(monkeypatch):
    """No pending add -> a plain message is a normal conversation (regression guard)."""
    monkeypatch.setattr(bot, "ALLOWED_CHAT_ID", 111)
    monkeypatch.setattr(bot, "PENDING_ADDS", {})
    manager = FakeSessionManager()
    monkeypatch.setattr(bot, "SESSION_MANAGER", manager)
    update, context = _update_context(111, "what's on my calendar?")

    asyncio.run(bot.handle_message(update, context))

    assert manager.asks == [(111, "what's on my calendar?", "implicit")]
