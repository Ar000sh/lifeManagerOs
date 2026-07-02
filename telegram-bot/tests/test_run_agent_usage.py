import asyncio
import sys
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import agent_runner  # noqa: E402


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
    monkeypatch.setattr(agent_runner, "ResultMessage", FakeResultMessage)
    monkeypatch.setattr(agent_runner, "AssistantMessage", type("NoMatch", (), {}))
    monkeypatch.setattr(agent_runner, "build_options", lambda stderr=None, chat_id=None: None)

    async def fake_query(*args, **kwargs):
        yield message

    monkeypatch.setattr(agent_runner, "query", lambda *a, **k: fake_query())


def test_run_agent_extracts_usage(monkeypatch):
    msg = FakeResultMessage("done", usage={"input_tokens": 5, "output_tokens": 7},
                            total_cost_usd=0.02)
    _patch_stream(monkeypatch, msg)
    res = asyncio.run(agent_runner.run_agent("/today"))
    assert res.reply == "done"
    assert res.input_tokens == 5
    assert res.output_tokens == 7
    assert res.cost_usd == 0.02


def test_run_agent_handles_missing_usage(monkeypatch):
    msg = FakeResultMessage("ok")  # no usage, no cost
    _patch_stream(monkeypatch, msg)
    res = asyncio.run(agent_runner.run_agent("hi"))
    assert res.reply == "ok"
    assert res.input_tokens is None
    assert res.output_tokens is None
    assert res.cost_usd is None


def test_run_agent_extracts_usage_from_object(monkeypatch):
    msg = FakeResultMessage("complete", usage=SimpleNamespace(input_tokens=3, output_tokens=4),
                            total_cost_usd=0.05)
    _patch_stream(monkeypatch, msg)
    res = asyncio.run(agent_runner.run_agent("/add"))
    assert res.reply == "complete"
    assert res.input_tokens == 3
    assert res.output_tokens == 4
    assert res.cost_usd == 0.05


def test_run_agent_includes_claude_stderr_on_failure(monkeypatch):
    monkeypatch.setattr(agent_runner, "build_options", agent_runner.build_options)

    async def fake_stream(options):
        options.stderr("API Error: credit balance is too low\n")
        raise RuntimeError("Claude Code returned an error result: success")
        yield  # pragma: no cover

    def fake_query(*, prompt, options):
        return fake_stream(options)

    monkeypatch.setattr(agent_runner, "query", fake_query)

    try:
        asyncio.run(agent_runner.run_agent("/today"))
    except RuntimeError as exc:
        message = str(exc)
    else:
        raise AssertionError("run_agent should have raised")

    assert "Claude Code returned an error result: success" in message
    assert "Claude stderr:" in message
    assert "credit balance is too low" in message


def test_run_agent_explains_misleading_success_error_without_stderr(monkeypatch):
    monkeypatch.setattr(agent_runner, "build_options", agent_runner.build_options)

    async def fake_stream(options):
        raise RuntimeError("Claude Code returned an error result: success")
        yield  # pragma: no cover

    monkeypatch.setattr(agent_runner, "query", lambda *, prompt, options: fake_stream(options))

    try:
        asyncio.run(agent_runner.run_agent("/today"))
    except RuntimeError as exc:
        message = str(exc)
    else:
        raise AssertionError("run_agent should have raised")

    assert "Claude Code returned an error result: success" in message
    assert "did not expose a detailed error" in message
