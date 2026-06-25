import asyncio
import sys
from pathlib import Path
from unittest.mock import AsyncMock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import bot  # noqa: E402


class StopAfterOneCleanup(Exception):
    pass


def test_cleanup_loop_calls_expire_idle(monkeypatch):
    fake_bot = AsyncMock()
    manager = AsyncMock()
    manager.expire_idle = AsyncMock(side_effect=StopAfterOneCleanup)
    monkeypatch.setattr(bot, "SESSION_MANAGER", manager)

    try:
        asyncio.run(bot.cleanup_sessions_loop(fake_bot, interval_seconds=0))
    except StopAfterOneCleanup:
        pass

    manager.expire_idle.assert_awaited_once()


def test_cleanup_loop_notifies_expired_chats(monkeypatch):
    """Each reaped session gets a Telegram heads-up that it timed out."""
    fake_bot = AsyncMock()
    manager = AsyncMock()
    # First sweep reports chat 123 expired; second sweep stops the loop.
    manager.expire_idle = AsyncMock(side_effect=[[123], StopAfterOneCleanup])
    monkeypatch.setattr(bot, "SESSION_MANAGER", manager)

    try:
        asyncio.run(bot.cleanup_sessions_loop(fake_bot, interval_seconds=0))
    except StopAfterOneCleanup:
        pass

    fake_bot.send_message.assert_awaited_once()
    assert fake_bot.send_message.await_args.kwargs["chat_id"] == 123


def test_cleanup_loop_survives_a_failed_send(monkeypatch):
    """A send that raises must be swallowed so one bad chat can't kill the loop."""
    fake_bot = AsyncMock()
    fake_bot.send_message = AsyncMock(side_effect=RuntimeError("telegram down"))
    manager = AsyncMock()
    manager.expire_idle = AsyncMock(side_effect=[[123], StopAfterOneCleanup])
    monkeypatch.setattr(bot, "SESSION_MANAGER", manager)

    # The RuntimeError from send_message must NOT propagate; only our sentinel does.
    try:
        asyncio.run(bot.cleanup_sessions_loop(fake_bot, interval_seconds=0))
    except StopAfterOneCleanup:
        pass

    # Loop reached the second sweep, proving it kept going past the failed send.
    assert manager.expire_idle.await_count == 2
