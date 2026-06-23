import asyncio
import sys
from pathlib import Path
from unittest.mock import AsyncMock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import bot  # noqa: E402


class StopAfterOneCleanup(Exception):
    pass


def test_cleanup_loop_calls_expire_idle(monkeypatch):
    manager = AsyncMock()
    manager.expire_idle = AsyncMock(side_effect=StopAfterOneCleanup)
    monkeypatch.setattr(bot, "SESSION_MANAGER", manager)

    try:
        asyncio.run(bot.cleanup_sessions_loop(interval_seconds=0))
    except StopAfterOneCleanup:
        pass

    manager.expire_idle.assert_awaited_once()
