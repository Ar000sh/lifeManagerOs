"""Regression test for the production MCP outage.

Commit cf93e09 set `tools=["Read", "Glob", "Grep"]` in build_options(). In the
Claude Agent SDK, `tools` controls which tools are *available* at all (not just
auto-approved), so that whitelist silently excluded the programmatic Notion /
Google Calendar MCP servers — the deployed bot reported "I don't have access to
the Notion or Google Calendar MCP tools." The fix: never gate availability with
`tools`; rely on allowed_tools + permission_mode="dontAsk", and strip write/exec
built-ins via disallowed_tools instead.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import agent_runner  # noqa: E402


def _options(monkeypatch):
    # build_options reads these module-level globals to decide which MCP servers
    # to register; set them so both servers are configured. The SDK adapter now
    # lives in agent_runner (split out of bot.py during the live-conversations work).
    monkeypatch.setattr(agent_runner, "NOTION_TOKEN", "ntn_test_token")
    monkeypatch.setattr(agent_runner, "GOOGLE_OAUTH_CREDENTIALS", "/app/secrets/gcp-oauth.keys.json")
    monkeypatch.setattr(agent_runner, "GOOGLE_CALENDAR_MCP_TOKEN_PATH", "/app/secrets/tokens")
    return agent_runner.build_options()


def test_mcp_tools_are_not_gated_by_tools_field(monkeypatch):
    """`tools` must stay unset — a list there excludes the MCP servers."""
    opts = _options(monkeypatch)
    # The regression was `tools=["Read", "Glob", "Grep"]`. Anything that restricts
    # the available built-in set to a plain list re-introduces the outage.
    assert getattr(opts, "tools", None) is None


def test_both_mcp_servers_are_registered_and_allowed(monkeypatch):
    opts = _options(monkeypatch)
    assert set(opts.mcp_servers) == {"notion-api", "google-calendar", "lifeos"}
    assert "mcp__notion-api" in opts.allowed_tools
    assert "mcp__google-calendar" in opts.allowed_tools
    assert "mcp__lifeos" in opts.allowed_tools


def test_filesystem_stays_read_only(monkeypatch):
    """Read-only intent is preserved via disallowed_tools, not via `tools`."""
    opts = _options(monkeypatch)
    for write_tool in ("Bash", "Write", "Edit"):
        assert write_tool in opts.disallowed_tools
    assert opts.permission_mode == "dontAsk"
