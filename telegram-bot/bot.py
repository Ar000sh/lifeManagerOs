"""
Life OS — Telegram bot starter.

Bridges Telegram <-> your Claude Code skills (/today, /week, /add, ...) using the
Claude Agent SDK. Runs headless on your *subscription* (no ANTHROPIC_API_KEY).

Local testing uses long-polling, so you do NOT need a public URL or webhook.

Flow:
    you message the bot  ->  this server  ->  Claude Agent SDK runs the skill
                          <-  reply text   <-  (loads CLAUDE.md + .claude/commands)
"""

import os
import sys
import logging
from dataclasses import dataclass
from pathlib import Path
from time import perf_counter

from dotenv import load_dotenv
from telegram import Update
from telegram.constants import ChatAction
from telegram.ext import (
    Application,
    MessageHandler,
    ContextTypes,
    filters,
)

from claude_agent_sdk import (
    query,
    ClaudeAgentOptions,
    AssistantMessage,
    TextBlock,
    ResultMessage,
)

import telemetry

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
load_dotenv()

TELEGRAM_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
ALLOWED_CHAT_ID = int(os.environ.get("ALLOWED_CHAT_ID", "0") or "0")
# Default: the parent folder of this bot dir == your lifeMg project root.
PROJECT_DIR = os.environ.get("PROJECT_DIR", str(Path(__file__).resolve().parent.parent))
CLAUDE_MODEL = os.environ.get("CLAUDE_MODEL", "").strip() or None
NOTION_TOKEN = os.environ.get("NOTION_TOKEN", "").strip()
GOOGLE_OAUTH_CREDENTIALS = os.environ.get("GOOGLE_OAUTH_CREDENTIALS", "").strip()
GOOGLE_CALENDAR_MCP_TOKEN_PATH = os.environ.get("GOOGLE_CALENDAR_MCP_TOKEN_PATH", "").strip()

# Max characters per Telegram message.
TELEGRAM_MAX = 4096

logging.basicConfig(
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger("lifeos-bot")


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
    """One agent turn's outcome: the reply text plus best-effort usage."""
    reply: str
    input_tokens: int | None = None
    output_tokens: int | None = None
    cost_usd: float | None = None


def _extract_usage(message):
    """Best-effort pull of token + cost telemetry off a ResultMessage.

    Field names are read defensively; anything missing stays None so a change
    in the SDK's shape can never break message handling. Confirm the real field
    names against the installed claude_agent_sdk during implementation.
    """
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


# ---------------------------------------------------------------------------
# Telegram handlers
# ---------------------------------------------------------------------------
_KNOWN_SKILLS = {"today", "week", "add"}


def detect_skill(text: str) -> str:
    stripped = text.strip()
    if "/" not in stripped:
        return "chat"
    # Skip [0]: the text before the first "/" wasn't preceded by a slash, so its
    # first word can't be a command. Every later chunk starts right after a "/".
    for chunk in stripped.split("/")[1:]:
        words = chunk.split()
        if words and words[0].lower() in _KNOWN_SKILLS:
            return words[0].lower()
    return "other"


def split_for_telegram(text: str) -> list[str]:
    """Telegram caps messages at 4096 chars; split on line boundaries."""
    if len(text) <= TELEGRAM_MAX:
        return [text]
    parts, current = [], ""
    for line in text.split("\n"):
        # a single line longer than the limit: hard-split it
        if len(line) > TELEGRAM_MAX:
            if current:
                # if we have line that is longer than the limit and we already have something in the current before
                # we need to add it as a chunk so we can keep the correct ordering of the text
                parts.append(current)
                current = ""
            # Add chucks until the line is shorter that the limit
            while len(line) > TELEGRAM_MAX:
                parts.append(line[:TELEGRAM_MAX])
                line = line[TELEGRAM_MAX:]
        # till here we have made sure that the line on its own is shorter than the limit
        # normal case: pack the line into the current chunk
        if len(current) + len(line) + 1 > TELEGRAM_MAX:
            if current:
            # Same thing applies here we add the current to keep the correct ordering of the text
                parts.append(current)
            current = line
        else:
            current = f"{current}\n{line}" if current else line
    if current:
        parts.append(current)
    return parts


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = update.effective_chat.id
    text = (update.message.text or "").strip()
    if not text:
        return

    if chat_id != ALLOWED_CHAT_ID:
        logger.warning("Ignoring message from unauthorized chat id %s", chat_id)
        return

    # --- run the agent (timed + measured) --------------------------------
    skill = detect_skill(text)
    logger.info("Prompt: %s", text)
    await context.bot.send_chat_action(chat_id=chat_id, action=ChatAction.TYPING)

    t0 = perf_counter()
    result = None
    status = "error"  # safe default; overwritten to "ok" on success
    try:
        result = await run_agent(text)
        reply = result.reply
        status = "ok"
    except Exception as exc:  # noqa: BLE001 - surface any error to the chat
        logger.exception("Agent run failed")
        reply = f"⚠️ Error running agent:\n{exc}"
        status = "error"
    finally:
        telemetry.record_run(skill, status, perf_counter() - t0, usage=result)

    for chunk in split_for_telegram(reply):
        await update.message.reply_text(chunk)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------
def main() -> None:
    if not TELEGRAM_TOKEN:
        raise SystemExit("TELEGRAM_BOT_TOKEN is missing.")

    telemetry.init_telemetry()

    app = Application.builder().token(TELEGRAM_TOKEN).build()
    # filters.TEXT matches plain text AND slash-commands like /today, /week.
    app.add_handler(MessageHandler(filters.TEXT, handle_message))

    logger.info("Bot is running (long-polling). Press Ctrl+C to stop.")
    try:
        app.run_polling(allowed_updates=Update.ALL_TYPES)
    finally:
        telemetry.shutdown_telemetry()


if __name__ == "__main__":
    main()
