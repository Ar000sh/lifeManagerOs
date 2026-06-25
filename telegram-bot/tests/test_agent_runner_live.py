import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import agent_runner  # noqa: E402


class FakeAssistantMessage:
    def __init__(self, text):
        self.content = [agent_runner.TextBlock(text=text)]


class FakeResultMessage:
    def __init__(self, result=None, usage=None, total_cost_usd=None):
        self.result = result
        self.usage = usage
        self.total_cost_usd = total_cost_usd


class FakeSDKClient:
    def __init__(self, options):
        self.options = options
        self.connected = False
        self.disconnected = False
        self.interrupted = False
        self.prompts = []

    async def connect(self):
        self.connected = True

    async def query(self, prompt):
        self.prompts.append(prompt)

    async def receive_response(self):
        yield FakeAssistantMessage("assistant text")
        yield FakeResultMessage(
            result="final text",
            usage={"input_tokens": 1, "output_tokens": 2},
            total_cost_usd=0.03,
        )

    async def interrupt(self):
        self.interrupted = True

    async def disconnect(self):
        self.disconnected = True


def test_live_agent_client_connects_and_asks(monkeypatch):
    monkeypatch.setattr(agent_runner, "AssistantMessage", FakeAssistantMessage)
    monkeypatch.setattr(agent_runner, "ResultMessage", FakeResultMessage)
    client = agent_runner.LiveAgentClient(
        options_factory=lambda stderr=None: "options",
        client_cls=FakeSDKClient,
    )

    result = asyncio.run(_connect_and_ask(client, "hello"))

    assert client._client.connected is True
    assert client._client.prompts == ["hello"]
    assert result.reply == "final text"
    assert result.input_tokens == 1
    assert result.output_tokens == 2
    assert result.cost_usd == 0.03


async def _connect_and_ask(client, prompt):
    await client.connect()
    return await client.ask(prompt)


def test_live_agent_client_interrupt_and_disconnect():
    client = agent_runner.LiveAgentClient(
        options_factory=lambda stderr=None: "options",
        client_cls=FakeSDKClient,
    )

    async def run():
        await client.connect()
        # Grab the underlying SDK client before disconnect(), which releases the
        # adapter's reference (sets _client back to None so a later connect()
        # rebuilds a fresh connection instead of reusing a dead one).
        underlying = client._client
        await client.interrupt()
        await client.disconnect()
        return underlying

    underlying = asyncio.run(run())

    assert underlying.interrupted is True
    assert underlying.disconnected is True
    assert client._client is None
