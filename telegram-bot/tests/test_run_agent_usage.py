import asyncio
import sys
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import bot  # noqa: E402


class FakeResultMessage:
    """Stand-in for the SDK ResultMessage with usage + cost."""
    def __init__(self, result, usage=None, total_cost_usd=None):
        self.result = result
        if usage is not None:
            self.usage = usage
        if total_cost_usd is not None:
            self.total_cost_usd = total_cost_usd


def _patch_stream(monkeypatch, message):
    # Make isinstance(message, ResultMessage) true and AssistantMessage never match.
    monkeypatch.setattr(bot, "ResultMessage", FakeResultMessage)
    monkeypatch.setattr(bot, "AssistantMessage", type("NoMatch", (), {}))
    monkeypatch.setattr(bot, "build_options", lambda: None)

    async def fake_query(*args, **kwargs):
        yield message

    monkeypatch.setattr(bot, "query", lambda *a, **k: fake_query())


def test_run_agent_extracts_usage(monkeypatch):
    msg = FakeResultMessage("done", usage={"input_tokens": 5, "output_tokens": 7},
                            total_cost_usd=0.02)
    _patch_stream(monkeypatch, msg)
    res = asyncio.run(bot.run_agent("/today"))
    assert res.reply == "done"
    assert res.input_tokens == 5
    assert res.output_tokens == 7
    assert res.cost_usd == 0.02


def test_run_agent_handles_missing_usage(monkeypatch):
    msg = FakeResultMessage("ok")  # no usage, no cost
    _patch_stream(monkeypatch, msg)
    res = asyncio.run(bot.run_agent("hi"))
    assert res.reply == "ok"
    assert res.input_tokens is None
    assert res.output_tokens is None
    assert res.cost_usd is None


def test_run_agent_extracts_usage_from_object(monkeypatch):
    msg = FakeResultMessage("complete", usage=SimpleNamespace(input_tokens=3, output_tokens=4),
                            total_cost_usd=0.05)
    _patch_stream(monkeypatch, msg)
    res = asyncio.run(bot.run_agent("/add"))
    assert res.reply == "complete"
    assert res.input_tokens == 3
    assert res.output_tokens == 4
    assert res.cost_usd == 0.05
