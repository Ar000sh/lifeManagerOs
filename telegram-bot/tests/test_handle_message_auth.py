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
    record = MagicMock()
    monkeypatch.setattr(bot.telemetry, "record_run", record)
    update, context = _update_context(chat_id=999)
    asyncio.run(bot.handle_message(update, context))
    run_agent.assert_not_called()
    update.message.reply_text.assert_not_called()
    record.assert_not_called()


def test_authorized_chat_runs_agent_replies_and_records(monkeypatch):
    monkeypatch.setattr(bot, "ALLOWED_CHAT_ID", 111)
    run_agent = AsyncMock(return_value=bot.AgentResult(reply="hi back"))
    monkeypatch.setattr(bot, "run_agent", run_agent)
    record = MagicMock()
    monkeypatch.setattr(bot.telemetry, "record_run", record)
    update, context = _update_context(chat_id=111)
    asyncio.run(bot.handle_message(update, context))
    run_agent.assert_awaited_once_with("/today")
    update.message.reply_text.assert_awaited_once_with("hi back")
    record.assert_called_once()
    assert record.call_args.args[0] == "today"   # skill
    assert record.call_args.args[1] == "ok"      # status


def test_error_path_records_error_and_still_replies(monkeypatch):
    monkeypatch.setattr(bot, "ALLOWED_CHAT_ID", 111)
    run_agent = AsyncMock(side_effect=RuntimeError("boom"))
    monkeypatch.setattr(bot, "run_agent", run_agent)
    record = MagicMock()
    monkeypatch.setattr(bot.telemetry, "record_run", record)
    update, context = _update_context(chat_id=111, text="/week")
    asyncio.run(bot.handle_message(update, context))
    update.message.reply_text.assert_awaited()
    sent = update.message.reply_text.await_args.args[0]
    assert "Error" in sent
    record.assert_called_once()
    assert record.call_args.args[0] == "week"    # skill
    assert record.call_args.args[1] == "error"   # status
