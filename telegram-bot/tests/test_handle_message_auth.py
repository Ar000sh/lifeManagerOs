import asyncio
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import bot  # noqa: E402


def _update_context(chat_id, text="/today"):
    update = MagicMock()
    update.effective_chat.id = chat_id
    update.message.text = text
    update.message.reply_text = AsyncMock()
    context = MagicMock()
    context.bot.send_chat_action = AsyncMock()
    return update, context


def test_unauthorized_chat_is_ignored(monkeypatch):
    monkeypatch.setattr(bot, "ALLOWED_CHAT_ID", 111)
    run_agent = AsyncMock()
    monkeypatch.setattr(bot, "run_agent", run_agent)
    update, context = _update_context(chat_id=999)
    asyncio.run(bot.handle_message(update, context))
    run_agent.assert_not_called()
    update.message.reply_text.assert_not_called()


def test_authorized_chat_runs_agent_and_replies(monkeypatch):
    monkeypatch.setattr(bot, "ALLOWED_CHAT_ID", 111)
    run_agent = AsyncMock(return_value="hi back")
    monkeypatch.setattr(bot, "run_agent", run_agent)
    update, context = _update_context(chat_id=111)
    asyncio.run(bot.handle_message(update, context))
    run_agent.assert_awaited_once_with("/today")
    update.message.reply_text.assert_awaited_once_with("hi back")
