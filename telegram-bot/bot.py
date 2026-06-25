import os
import asyncio
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
from sessions import SessionManager, compose_command_conversation_prompt

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

# One process-wide registry of live conversations, keyed by Telegram chat id.
SESSION_MANAGER = SessionManager()


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

    route = classify_message(text)
    logger.info("Prompt: %s", text)
    logger.info("Route %s", route)

    # --- session control messages (no agent run, no telemetry timing) ----
    if route.kind == "stop":
        await SESSION_MANAGER.stop(chat_id)
        await update.message.reply_text("Conversation stopped.")
        return

    if route.kind == "chat" and route.followup_text is None:
        # Bare /chat just opens a 30-min session; nothing is sent to Claude yet.
        SESSION_MANAGER.get_or_create(chat_id, "chat")
        await update.message.reply_text("Chat mode started.")
        return

    # --- run the agent (timed + measured) --------------------------------
    await context.bot.send_chat_action(chat_id=chat_id, action=ChatAction.TYPING)

    t0 = perf_counter()
    result = None
    status = "error"  # safe default; overwritten to "ok" on success
    session_mode = "standalone"
    session_event = None
    try:
        if route.kind == "standalone_command":
            # Bare /today, /week, /add: one-shot, never touches a live session.
            result = await run_agent(route.command_text or text)
            reply = result.reply
            session_mode = "standalone"
        elif route.kind == "command_conversation":
            # "/today help me ...": run the command one-shot, then hand its
            # result + the follow-up to the implicit live session as context.
            command_result = await run_agent(route.command_text or text)
            prompt = compose_command_conversation_prompt(
                route.command_text or text,
                command_result.reply,
                route.followup_text or "",
            )
            result, session_event = await SESSION_MANAGER.ask(chat_id, prompt, mode="implicit")
            reply = result.reply
            session_mode = "implicit"
        else:
            # Plain text -> implicit session; /chat <text> -> chat session.
            mode = "chat" if route.kind == "chat" else "implicit"
            prompt = route.followup_text or text
            result, session_event = await SESSION_MANAGER.ask(chat_id, prompt, mode=mode)
            reply = result.reply
            session_mode = mode
        status = "ok"
    except Exception as exc:  # noqa: BLE001 - surface any error to the chat
        logger.exception("Agent run failed")
        reply = f"⚠️ Error running agent:\n{exc}"
        status = "error"
    finally:
        telemetry.record_run(
            route.skill,
            status,
            perf_counter() - t0,
            usage=result,
            session_mode=session_mode,
            session_event=session_event,
        )

    for chunk in split_for_telegram(reply):
        await update.message.reply_text(chunk)


async def cleanup_sessions_loop(bot, interval_seconds: int = 60) -> None:
    while True:
        await asyncio.sleep(interval_seconds)
        expired = await SESSION_MANAGER.expire_idle()
        for chat_id in expired:
            logger.info("Expired idle conversation session for chat id %s", chat_id)
            try:
                await bot.send_message(
                    chat_id=chat_id,
                    text="💤 Conversation timed out after inactivity.",
                )
            except Exception:  # noqa: BLE001 - never let one bad send kill the loop
                logger.exception("Failed to notify chat %s of idle timeout", chat_id)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------
async def _post_init(app) -> None:
    # Launch the idle-cleanup sweep once the event loop is running; stash the
    # task handle so we can cancel it cleanly at shutdown.
    app.bot_data["session_cleanup_task"] = asyncio.create_task(cleanup_sessions_loop(app.bot))


async def _post_shutdown(app) -> None:
    task = app.bot_data.get("session_cleanup_task")
    if task:
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass


def main() -> None:
    if not TELEGRAM_TOKEN:
        raise SystemExit("TELEGRAM_BOT_TOKEN is missing.")

    telemetry.init_telemetry()

    app = (
        Application.builder()
        .token(TELEGRAM_TOKEN)
        .post_init(_post_init)
        .post_shutdown(_post_shutdown)
        .build()
    )
    # filters.TEXT matches plain text AND slash-commands like /today, /week.
    app.add_handler(MessageHandler(filters.TEXT, handle_message))

    logger.info("Bot is running (long-polling). Press Ctrl+C to stop.")
    try:
        app.run_polling(allowed_updates=Update.ALL_TYPES)
    finally:
        telemetry.shutdown_telemetry()


if __name__ == "__main__":
    main()
