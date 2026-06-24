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
import logging
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

from agent_runner import AgentResult, run_agent
from routing import classify_message, detect_skill

import telemetry

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
load_dotenv()

TELEGRAM_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
ALLOWED_CHAT_ID = int(os.environ.get("ALLOWED_CHAT_ID", "0") or "0")

# Max characters per Telegram message.
TELEGRAM_MAX = 4096

logging.basicConfig(
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger("lifeos-bot")


# ---------------------------------------------------------------------------
# Telegram handlers
# ---------------------------------------------------------------------------
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
    # Classify now so telemetry uses the route's skill label. Behaviour is still
    # one-shot for every message; sessions get wired in a later task.
    route = classify_message(text)
    skill = route.skill
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
