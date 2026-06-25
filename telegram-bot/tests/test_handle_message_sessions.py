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
