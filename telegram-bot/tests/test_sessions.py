import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from agent_runner import AgentResult  # noqa: E402
from sessions import SessionManager, compose_command_conversation_prompt  # noqa: E402


class FakeLiveClient:
    def __init__(self):
        self.prompts = []
        self.disconnected = False
        self.interrupted = False

    async def ask(self, prompt):
        self.prompts.append(prompt)
        return AgentResult(reply=f"reply: {prompt}")

    async def interrupt(self):
        self.interrupted = True

    async def disconnect(self):
        self.disconnected = True


def test_creates_and_reuses_implicit_session():
    created = []
    manager = SessionManager(client_factory=lambda: _new_client(created), now=lambda: 100.0)

    async def run():
        first, event1 = await manager.ask(111, "hello")
        second, event2 = await manager.ask(111, "again")
        return first, event1, second, event2

    first, event1, second, event2 = asyncio.run(run())

    assert first.reply == "reply: hello"
    assert second.reply == "reply: again"
    assert event1 == "created"
    assert event2 == "reused"
    assert len(created) == 1
    assert created[0].prompts == ["hello", "again"]


def test_upgrades_implicit_to_chat():
    created = []
    manager = SessionManager(client_factory=lambda: _new_client(created), now=lambda: 100.0)

    async def run():
        await manager.ask(111, "hello")
        await manager.ask(111, "long mode", mode="chat")

    asyncio.run(run())

    session = manager.sessions[111]
    assert session.mode == "chat"
    assert session.timeout_seconds == 30 * 60
    assert len(created) == 1


def test_stop_interrupts_and_removes_session():
    created = []
    manager = SessionManager(client_factory=lambda: _new_client(created), now=lambda: 100.0)

    async def run():
        await manager.ask(111, "hello")
        stopped = await manager.stop(111)
        return stopped

    stopped = asyncio.run(run())

    assert stopped is True
    assert 111 not in manager.sessions
    assert created[0].interrupted is True
    assert created[0].disconnected is True


def test_expire_idle_disconnects_implicit_after_10_minutes():
    created = []
    now_value = 100.0
    manager = SessionManager(client_factory=lambda: _new_client(created), now=lambda: now_value)

    async def run():
        await manager.ask(111, "hello")
        return await manager.expire_idle(now=100.0 + 601)

    expired = asyncio.run(run())

    assert expired == [111]
    assert 111 not in manager.sessions
    assert created[0].disconnected is True


def test_command_conversation_prompt_contains_command_result_and_followup():
    prompt = compose_command_conversation_prompt("/today", "Task A", "help me prioritize")
    assert "/today" in prompt
    assert "Task A" in prompt
    assert "help me prioritize" in prompt


def _new_client(created):
    client = FakeLiveClient()
    created.append(client)
    return client
