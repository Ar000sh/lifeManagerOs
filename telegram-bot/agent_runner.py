"""
Claude Agent SDK adapter for the Life OS bot.

Owns everything about *talking to Claude*:
  - SDK option building (which MCP servers, tools, model, project dir)
  - the one-shot `run_agent()` path used by standalone /today, /week, /add
  - the `LiveAgentClient` adapter used by multi-turn conversations

`bot.py` imports from here so the Telegram layer never touches the SDK directly.
"""

import logging
import os
import sys
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv
from claude_agent_sdk import (
    query,
    ClaudeSDKClient,
    ClaudeAgentOptions,
    AssistantMessage,
    UserMessage,
    TextBlock,
    ToolUseBlock,
    ToolResultBlock,
    ResultMessage,
)

logger = logging.getLogger("lifeos-bot.agent")

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


def build_options(stderr=None, chat_id=None, lifeos_only=False) -> ClaudeAgentOptions:
    """Options that make the headless agent behave like your Claude Code project.

    ``lifeos_only=True`` scopes the run to the deterministic **skill lane**: only the
    lifeos MCP server is registered (plus read-only Read/Glob/Grep), and the raw
    ``notion-api`` / ``google-calendar`` servers are dropped entirely. This is how
    ``/add`` is made bypass-proof — the agent physically cannot reach the raw Notion
    tool to route around lifeos' rules (e.g. the required ``due_date``). Prompt-steering
    in ``add.md`` alone was not enough; see docs/superpowers/2026-07-08-skill-tool-scoping.md.
    """
    # MCP servers declared *programmatically* are trusted in a non-interactive run
    # (project .mcp.json servers get silently skipped here).
    mcp_servers: dict = {}

    # The raw Notion / Calendar servers are only wired for the flexible chat lane.
    # The skill lane (lifeos_only) omits them so a skill can't bypass lifeos.
    if not lifeos_only:
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

    # lifeos — our own MCP: deterministic get_today/get_week/add_record/create_event over
    # the map. Registered PROGRAMMATICALLY (project .mcp.json is skipped in headless runs).
    lifeos_env = {
        "NOTION_TOKEN": NOTION_TOKEN,
        "GOOGLE_OAUTH_CREDENTIALS": GOOGLE_OAUTH_CREDENTIALS,
        "GOOGLE_CALENDAR_MCP_TOKEN_PATH": GOOGLE_CALENDAR_MCP_TOKEN_PATH,
        "LIFEOS_MAP_STORE": os.environ.get("LIFEOS_MAP_STORE", "file"),
        "LIFEOS_BLOB_ACCOUNT_URL": os.environ.get("LIFEOS_BLOB_ACCOUNT_URL", ""),
        "LIFEOS_MAP_CONTAINER": os.environ.get("LIFEOS_MAP_CONTAINER", "maps"),
        "LIFEOS_IDENTITY": str(chat_id) if chat_id is not None else "",
    }
    # Explicit map dir for the file store when the server can't derive it from its install
    # location (non-editable install in the container). Passed only when set; local dev
    # (editable install) lets the server use its own repo-relative default.
    _map_dir = os.environ.get("LIFEOS_MAP_DIR")
    if _map_dir:
        lifeos_env["LIFEOS_MAP_DIR"] = _map_dir
    # Azure service-principal creds for the blob map store when running off-VM (local
    # docker / dev). The spawned server gets an explicit env dict, so pass these through
    # only when set. On the VM they're unset — DefaultAzureCredential uses the managed
    # identity (IMDS) instead, so injecting empty values here would misfire.
    for _azure_key in ("AZURE_CLIENT_ID", "AZURE_TENANT_ID", "AZURE_CLIENT_SECRET"):
        _azure_val = os.environ.get(_azure_key)
        if _azure_val:
            lifeos_env[_azure_key] = _azure_val
    mcp_servers["lifeos"] = {
        "type": "stdio", "command": sys.executable,
        "args": ["-m", "lifeos_mcp.server"], "env": lifeos_env,
    }

    # Skill lane: lifeos + read-only builtins only. Chat lane: also allow the raw
    # servers. allowed_tools must not name servers we didn't register above, or the
    # skill lane would still list tools it can't reach.
    allowed_tools = ["Read", "Glob", "Grep", "mcp__lifeos"]
    if not lifeos_only:
        allowed_tools += ["mcp__notion-api", "mcp__google-calendar"]

    return ClaudeAgentOptions(
        cwd=PROJECT_DIR,
        # Load CLAUDE.md, .claude/commands skills, and any hosted connectors from your
        # Claude login (user settings).
        setting_sources=["user", "project", "local"],
        system_prompt={"type": "preset", "preset": "claude_code"},
        # Default-deny: with permission_mode="dontAsk", any tool NOT pre-approved in
        # allowed_tools below is denied (headless, so this denies instead of prompting).
        permission_mode="dontAsk",
        allowed_tools=allowed_tools,
        # Read-only filesystem: remove the write/exec built-ins from the agent's
        # context. Do NOT use `tools=[...]` to whitelist here — that field sets the
        # *available* tool set and silently EXCLUDES the MCP servers, which left the
        # bot with no Notion/Calendar access in production (SDK ClaudeAgentOptions:
        # `tools` = availability, `allowed_tools` = auto-approval).
        disallowed_tools=["Bash", "Write", "Edit", "NotebookEdit"],
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
    tools_used: list[str] = field(default_factory=list)
    # What each tool returned: [{"name", "is_error", "content"}]. Lets the bot tell a
    # completed /add (add_record/create_event -> created:true) from one that asked a
    # question (missing_required / ambiguous_destination) so it can hold a pending add.
    tool_results: list[dict] = field(default_factory=list)


def _tool_uses(message) -> list[str]:
    """Names of the tools the agent invoked in one AssistantMessage (e.g.
    ``mcp__lifeos__get_today``). Empty for non-assistant / text-only messages.
    Lets us prove which MCP server actually did the work — the lifeos tools vs a
    fallback to the raw Notion/Calendar servers or the model answering unaided."""
    if not isinstance(message, AssistantMessage):
        return []
    return [b.name for b in message.content if isinstance(b, ToolUseBlock)]


def _tool_results(message, limit: int = 400) -> list[dict]:
    """The results the tools returned, carried back in a UserMessage. Each is
    ``{tool_use_id, is_error, content}`` with content stringified + truncated, so
    we can see *what a tool returned* (e.g. add_record's ``missing_required``) —
    not just that it was called. ``tool_use_id`` correlates to a prior ToolUseBlock."""
    if not isinstance(message, UserMessage):
        return []
    out = []
    for b in message.content:
        if isinstance(b, ToolResultBlock):
            text = str(b.content)
            if len(text) > limit:
                text = text[:limit] + "…"
            out.append({"tool_use_id": b.tool_use_id,
                        "is_error": bool(b.is_error), "content": text})
    return out


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


async def run_agent(prompt: str, chat_id: int | None = None, lifeos_only: bool = False) -> AgentResult:
    """Run one agent turn and return its reply + best-effort usage metrics.

    ``lifeos_only=True`` runs in the deterministic skill lane (lifeos + read-only
    builtins, no raw notion-api/google-calendar) — used for ``/add``.
    """
    text_chunks: list[str] = []
    final_result: str | None = None
    input_tokens = output_tokens = cost_usd = None
    tools_used: list[str] = []
    tool_results: list[dict] = []
    name_by_id: dict[str, str] = {}
    stderr_chunks: list[str] = []

    try:
        async for message in query(
            prompt=prompt,
            options=build_options(stderr=stderr_chunks.append, chat_id=chat_id, lifeos_only=lifeos_only),
        ):
            if isinstance(message, AssistantMessage):
                for block in message.content:
                    if isinstance(block, TextBlock):
                        text_chunks.append(block.text)
                    elif isinstance(block, ToolUseBlock):
                        name_by_id[block.id] = block.name
                for name in _tool_uses(message):
                    logger.info("tool_use: %s", name)
                    tools_used.append(name)
            elif isinstance(message, UserMessage):
                for r in _tool_results(message):
                    name = name_by_id.get(r["tool_use_id"], r["tool_use_id"])
                    logger.info("tool_result: %s%s -> %s", name,
                                " [error]" if r["is_error"] else "", r["content"])
                    tool_results.append({"name": name, "is_error": r["is_error"],
                                         "content": r["content"]})
            elif isinstance(message, ResultMessage):
                final_result = getattr(message, "result", None)
                input_tokens, output_tokens, cost_usd = _extract_usage(message)
    except Exception as exc:
        raise RuntimeError(_format_agent_error(exc, stderr_chunks)) from exc

    reply = final_result or "\n".join(text_chunks).strip() or "(no response)"
    return AgentResult(reply, input_tokens, output_tokens, cost_usd, tools_used, tool_results)


class LiveAgentClient:
    """Adapter around a persistent ``ClaudeSDKClient`` for multi-turn chat.

    Unlike one-shot ``run_agent``/``query`` (a fresh, memoryless Claude per call),
    this holds one connection open so successive ``ask()`` calls share context.

    ``options_factory`` and ``client_cls`` are injectable so tests can swap in a
    fake SDK client and never touch the network or real Claude.
    """

    def __init__(self, options_factory=build_options, client_cls=ClaudeSDKClient, chat_id=None):
        self._options_factory = options_factory
        self._client_cls = client_cls
        self._chat_id = chat_id
        self._client = None

    async def connect(self) -> None:
        # Lazy + idempotent: build the underlying client once, on first use.
        if self._client is not None:
            return
        self._client = self._client_cls(self._options_factory(chat_id=self._chat_id))
        await self._client.connect()

    async def ask(self, prompt: str) -> AgentResult:
        await self.connect()
        await self._client.query(prompt)
        text_chunks: list[str] = []
        final_result: str | None = None
        input_tokens = output_tokens = cost_usd = None
        tools_used: list[str] = []
        name_by_id: dict[str, str] = {}

        async for message in self._client.receive_response():
            if isinstance(message, AssistantMessage):
                for block in message.content:
                    if isinstance(block, TextBlock):
                        text_chunks.append(block.text)
                    elif isinstance(block, ToolUseBlock):
                        name_by_id[block.id] = block.name
                for name in _tool_uses(message):
                    logger.info("tool_use: %s", name)
                    tools_used.append(name)
            elif isinstance(message, UserMessage):
                for r in _tool_results(message):
                    name = name_by_id.get(r["tool_use_id"], r["tool_use_id"])
                    logger.info("tool_result: %s%s -> %s", name,
                                " [error]" if r["is_error"] else "", r["content"])
            elif isinstance(message, ResultMessage):
                final_result = getattr(message, "result", None)
                input_tokens, output_tokens, cost_usd = _extract_usage(message)

        reply = final_result or "\n".join(text_chunks).strip() or "(no response)"
        return AgentResult(reply, input_tokens, output_tokens, cost_usd, tools_used)

    async def interrupt(self) -> None:
        if self._client is not None:
            await self._client.interrupt()

    async def disconnect(self) -> None:
        if self._client is not None:
            await self._client.disconnect()
            self._client = None
