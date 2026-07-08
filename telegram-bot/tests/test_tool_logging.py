import asyncio
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import agent_runner  # noqa: E402
from claude_agent_sdk import (  # noqa: E402
    AssistantMessage,
    TextBlock,
    ToolUseBlock,
    UserMessage,
    ToolResultBlock,
)


def test_tool_uses_extracts_names_from_assistant_message():
    msg = AssistantMessage(
        content=[
            ToolUseBlock(id="t1", name="mcp__lifeos__get_today", input={}),
            TextBlock(text="here is your day"),
        ],
        model="claude",
    )
    assert agent_runner._tool_uses(msg) == ["mcp__lifeos__get_today"]


def test_tool_uses_empty_for_text_only_or_other_message():
    text_only = AssistantMessage(content=[TextBlock(text="hi")], model="claude")
    assert agent_runner._tool_uses(text_only) == []
    assert agent_runner._tool_uses(object()) == []


class _FakeResult:
    def __init__(self, result):
        self.result = result


def test_run_agent_records_and_logs_tool_uses(monkeypatch, caplog):
    # Real AssistantMessage so isinstance matches; only ResultMessage is faked.
    monkeypatch.setattr(agent_runner, "ResultMessage", _FakeResult)
    monkeypatch.setattr(agent_runner, "build_options", lambda stderr=None, chat_id=None, lifeos_only=False: None)

    assistant = AssistantMessage(
        content=[ToolUseBlock(id="t1", name="mcp__lifeos__get_today", input={})],
        model="claude",
    )

    async def fake_query(*args, **kwargs):
        yield assistant
        yield _FakeResult("done")

    monkeypatch.setattr(agent_runner, "query", lambda *a, **k: fake_query())

    with caplog.at_level(logging.INFO, logger="lifeos-bot.agent"):
        res = asyncio.run(agent_runner.run_agent("/today"))

    assert res.reply == "done"
    assert res.tools_used == ["mcp__lifeos__get_today"]
    assert any("mcp__lifeos__get_today" in r.getMessage() for r in caplog.records)


def test_tool_results_extracts_id_error_and_content():
    msg = UserMessage(content=[
        ToolResultBlock(
            tool_use_id="t1",
            content="{'created': False, 'error': 'missing_required'}",
            is_error=False,
        ),
    ])
    out = agent_runner._tool_results(msg)
    assert len(out) == 1
    assert out[0]["tool_use_id"] == "t1"
    assert out[0]["is_error"] is False
    assert "missing_required" in out[0]["content"]


def test_tool_results_empty_for_non_user_message():
    assert agent_runner._tool_results(object()) == []


def test_run_agent_logs_tool_result_correlated_to_tool_name(monkeypatch, caplog):
    monkeypatch.setattr(agent_runner, "ResultMessage", _FakeResult)
    monkeypatch.setattr(agent_runner, "build_options", lambda stderr=None, chat_id=None, lifeos_only=False: None)

    assistant = AssistantMessage(
        content=[ToolUseBlock(id="t1", name="mcp__lifeos__add_record", input={})],
        model="claude",
    )
    user = UserMessage(content=[
        ToolResultBlock(
            tool_use_id="t1",
            content="{'created': False, 'error': 'missing_required', 'fields': ['due_date']}",
            is_error=False,
        ),
    ])

    async def fake_query(*args, **kwargs):
        yield assistant
        yield user
        yield _FakeResult("done")

    monkeypatch.setattr(agent_runner, "query", lambda *a, **k: fake_query())

    with caplog.at_level(logging.INFO, logger="lifeos-bot.agent"):
        res = asyncio.run(agent_runner.run_agent("/add"))

    msgs = "\n".join(r.getMessage() for r in caplog.records)
    assert res.reply == "done"
    assert "tool_result" in msgs
    assert "mcp__lifeos__add_record" in msgs  # name correlated from the tool_use id
    assert "missing_required" in msgs
