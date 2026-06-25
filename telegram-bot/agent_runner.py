"""
Claude Agent SDK adapter for the Life OS bot.

Owns everything about *talking to Claude*:
  - SDK option building (which MCP servers, tools, model, project dir)
  - the one-shot `run_agent()` path used by standalone /today, /week, /add
  - the `LiveAgentClient` adapter used by multi-turn conversations

`bot.py` imports from here so the Telegram layer never touches the SDK directly.
"""

import os
import sys
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv
from claude_agent_sdk import (
    query,
    ClaudeSDKClient,
    ClaudeAgentOptions,
    AssistantMessage,
    TextBlock,
    ResultMessage,
)

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
load_dotenv()

# Default: the parent folder of this bot dir == your lifeMg project root.
PROJECT_DIR = os.environ.get("PROJECT_DIR", str(Path(__file__).resolve().parent.parent))
CLAUDE_MODEL = os.environ.get("CLAUDE_MODEL", "").strip() or None
NOTION_TOKEN = os.environ.get("NOTION_TOKEN", "").strip()
GOOGLE_OAUTH_CREDENTIALS = os.environ.get("GOOGLE_OAUTH_CREDENTIALS", "").strip()
GOOGLE_CALENDAR_MCP_TOKEN_PATH = os.environ.get("GOOGLE_CALENDAR_MCP_TOKEN_PATH", "").strip()


# ---------------------------------------------------------------------------
# Claude Agent SDK
# ---------------------------------------------------------------------------
def _npx_stdio_server(package: str, env: dict) -> dict:
    """Build a cross-platform stdio MCP server config that runs an npx package."""
    if sys.platform == "win32":
        command, args = "cmd", ["/c", "npx", "-y", package]  # Windows: npx via cmd
    else:
        command, args = "npx", ["-y", package]               # Linux / macOS / Docker
    return {"type": "stdio", "command": command, "args": args, "env": env}


def _format_agent_error(exc: Exception, stderr_chunks: list[str]) -> str:
    message = str(exc)
    stderr_text = "".join(stderr_chunks).strip()
    if not stderr_text:
        if message == "Claude Code returned an error result: success":
            return (
                f"{message}\n\n"
                "Claude Code failed but the SDK did not expose a detailed error. "
                "Could possibly be due to Token Limits please Check Claude account limits/credits"
            )
        return message

    tail = stderr_text[-2000:]
    return f"{message}\n\nClaude stderr:\n{tail}"


def build_options(stderr=None) -> ClaudeAgentOptions:
    """Options that make the headless agent behave like your Claude Code project."""
    # MCP servers declared *programmatically* are trusted in a non-interactive run
    # (project .mcp.json servers get silently skipped here).
    mcp_servers: dict = {}

    # Notion — official API server with real property-filtered queries.
    if NOTION_TOKEN:
        mcp_servers["notion-api"] = _npx_stdio_server(
            "@notionhq/notion-mcp-server", {"NOTION_TOKEN": NOTION_TOKEN}
        )

    # Google Calendar — token-based server (replaces the laptop-only hosted connector
    # so the bot works on a server too). Authenticate once locally; see README.
    if GOOGLE_OAUTH_CREDENTIALS:
        gcal_env = {"GOOGLE_OAUTH_CREDENTIALS": GOOGLE_OAUTH_CREDENTIALS}
        if GOOGLE_CALENDAR_MCP_TOKEN_PATH:
            gcal_env["GOOGLE_CALENDAR_MCP_TOKEN_PATH"] = GOOGLE_CALENDAR_MCP_TOKEN_PATH
        mcp_servers["google-calendar"] = _npx_stdio_server(
            "@cocal/google-calendar-mcp", gcal_env
        )

    return ClaudeAgentOptions(
        cwd=PROJECT_DIR,
        # Load CLAUDE.md, .claude/commands skills, and any hosted connectors from your
        # Claude login (user settings).
        setting_sources=["user", "project", "local"],
        system_prompt={"type": "preset", "preset": "claude_code"},
        # Read-only filesystem: the bot organizes via the Notion/Calendar MCP
        tools=["Read", "Glob", "Grep"],
        # Default-deny instead of auto-approve-everything
        permission_mode="dontAsk",
        allowed_tools=[
            "Read", "Glob", "Grep",
            "mcp__notion-api",       # all Notion MCP tools (read + create/update)
            "mcp__google-calendar",  # all Google Calendar MCP tools
        ],
        model=CLAUDE_MODEL,
        mcp_servers=mcp_servers,
        stderr=stderr,
    )


@dataclass
class AgentResult:
    reply: str
    input_tokens: int | None = None
    output_tokens: int | None = None
    cost_usd: float | None = None


def _extract_usage(message):
    usage = getattr(message, "usage", None)
    input_tokens = output_tokens = None
    if isinstance(usage, dict):
        input_tokens = usage.get("input_tokens")
        output_tokens = usage.get("output_tokens")
    elif usage is not None:
        input_tokens = getattr(usage, "input_tokens", None)
        output_tokens = getattr(usage, "output_tokens", None)
    cost_usd = getattr(message, "total_cost_usd", None)
    return input_tokens, output_tokens, cost_usd


async def run_agent(prompt: str) -> AgentResult:
    """Run one agent turn and return its reply + best-effort usage metrics."""
    text_chunks: list[str] = []
    final_result: str | None = None
    input_tokens = output_tokens = cost_usd = None
    stderr_chunks: list[str] = []

    try:
        async for message in query(
            prompt=prompt,
            options=build_options(stderr=stderr_chunks.append),
        ):
            if isinstance(message, AssistantMessage):
                for block in message.content:
                    if isinstance(block, TextBlock):
                        text_chunks.append(block.text)
            elif isinstance(message, ResultMessage):
                final_result = getattr(message, "result", None)
                input_tokens, output_tokens, cost_usd = _extract_usage(message)
    except Exception as exc:
        raise RuntimeError(_format_agent_error(exc, stderr_chunks)) from exc

    reply = final_result or "\n".join(text_chunks).strip() or "(no response)"
    return AgentResult(reply, input_tokens, output_tokens, cost_usd)


class LiveAgentClient:
    """Adapter around a persistent ``ClaudeSDKClient`` for multi-turn chat.

    Unlike one-shot ``run_agent``/``query`` (a fresh, memoryless Claude per call),
    this holds one connection open so successive ``ask()`` calls share context.

    ``options_factory`` and ``client_cls`` are injectable so tests can swap in a
    fake SDK client and never touch the network or real Claude.
    """

    def __init__(self, options_factory=build_options, client_cls=ClaudeSDKClient):
        self._options_factory = options_factory
        self._client_cls = client_cls
        self._client = None

    async def connect(self) -> None:
        # Lazy + idempotent: build the underlying client once, on first use.
        if self._client is not None:
            return
        self._client = self._client_cls(self._options_factory())
        await self._client.connect()

    async def ask(self, prompt: str) -> AgentResult:
        await self.connect()
        await self._client.query(prompt)
        text_chunks: list[str] = []
        final_result: str | None = None
        input_tokens = output_tokens = cost_usd = None

        async for message in self._client.receive_response():
            if isinstance(message, AssistantMessage):
                for block in message.content:
                    if isinstance(block, TextBlock):
                        text_chunks.append(block.text)
            elif isinstance(message, ResultMessage):
                final_result = getattr(message, "result", None)
                input_tokens, output_tokens, cost_usd = _extract_usage(message)

        reply = final_result or "\n".join(text_chunks).strip() or "(no response)"
        return AgentResult(reply, input_tokens, output_tokens, cost_usd)

    async def interrupt(self) -> None:
        if self._client is not None:
            await self._client.interrupt()

    async def disconnect(self) -> None:
        if self._client is not None:
            await self._client.disconnect()
            self._client = None