"""
Live conversation sessions for the Life OS bot.

A `ConversationSession` is one ongoing chat for one Telegram chat_id: it owns a
LiveAgentClient (a persistent Claude connection) and tracks its mode and idle
time. `SessionManager` is the registry of those sessions keyed by chat_id.

Two modes, two idle timeouts:
  - "implicit": started by plain text, expires after 10 minutes of silence
  - "chat":     started by /chat, expires after 30 minutes of silence

The clock (`now`) is injectable so tests can fast-forward time without waiting.
"""

import asyncio
from dataclasses import dataclass, field
from time import monotonic
from typing import Callable, Literal
import logging
from agent_runner import AgentResult, LiveAgentClient

SessionMode = Literal["implicit", "chat"]

IMPLICIT_TIMEOUT_SECONDS = 10 * 60
CHAT_TIMEOUT_SECONDS = 30 * 60

logging.basicConfig(
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger("lifeos-bot")
def timeout_for_mode(mode: SessionMode) -> int:
    return CHAT_TIMEOUT_SECONDS if mode == "chat" else IMPLICIT_TIMEOUT_SECONDS


def compose_command_conversation_prompt(command: str, command_result: str, followup: str) -> str:
    """Stitch a one-shot command's output + the user's follow-up into one prompt.

    Used for mixed messages like "/today help me prioritize": we run /today
    standalone, then hand its result to the live session as context.
    """
    return (
        f"I ran {command} as a standalone command.\n\n"
        f"Command result:\n{command_result}\n\n"
        f"User follow-up:\n{followup}\n\n"
        "Use the command result as context and answer the follow-up."
    )


@dataclass
class ConversationSession:
    chat_id: int
    client: LiveAgentClient
    mode: SessionMode
    now: Callable[[], float] = monotonic
    lock: asyncio.Lock = field(default_factory=asyncio.Lock)
    created_at: float = field(init=False)
    last_activity: float = field(init=False)
    active: bool = False

    def __post_init__(self) -> None:
        self.created_at = self.now()
        self.last_activity = self.created_at

    @property
    def timeout_seconds(self) -> int:
        return timeout_for_mode(self.mode)

    def upgrade_to_chat(self) -> None:
        self.mode = "chat"
        self.touch()

    def touch(self) -> None:
        self.last_activity = self.now()

    def is_idle_expired(self, now: float) -> bool:
        # An in-flight turn is never reaped, even if it runs past the timeout.
        passed_time = now - self.last_activity
        logger.info("current sessions timeout %s and passed time %s", self.timeout_seconds, passed_time)
        return not self.active and (now - self.last_activity) > self.timeout_seconds

    async def ask(self, prompt: str) -> AgentResult:
        # The lock serialises turns: a second message can't start a turn on the
        # same Claude connection while the first is still streaming.
        async with self.lock:
            self.active = True
            self.touch()
            try:
                return await self.client.ask(prompt)
            finally:
                self.active = False
                self.touch()

    async def stop(self, interrupt: bool = True) -> None:
        if interrupt:
            await self.client.interrupt()
        await self.client.disconnect()


class SessionManager:
    def __init__(
        self,
        client_factory=LiveAgentClient,
        now: Callable[[], float] = monotonic,
    ):
        self.client_factory = client_factory
        self.now = now
        self.sessions: dict[int, ConversationSession] = {}

    def get_or_create(self, chat_id: int, mode: SessionMode = "implicit") -> tuple[ConversationSession, str]:
        session = self.sessions.get(chat_id)
        if session is None:
            session = ConversationSession(
                chat_id=chat_id, client=self.client_factory(chat_id=chat_id), mode=mode, now=self.now
            )
            self.sessions[chat_id] = session
            logger.info("created a new session")
            return session, "created"
        if mode == "chat" and session.mode != "chat":
            session.upgrade_to_chat()
            logger.info("update to a chat session")

            return session, "upgraded"
        session.touch()
        logger.info("reuse current session")
        return session, "reused"

    async def ask(self, chat_id: int, prompt: str, mode: SessionMode = "implicit") -> tuple[AgentResult, str]:
        session, event = self.get_or_create(chat_id, mode)
        result = await session.ask(prompt)
        return result, event

    async def stop(self, chat_id: int) -> bool:
        session = self.sessions.pop(chat_id, None)
        if session is None:
            return False
        await session.stop(interrupt=True)
        return True

    async def expire_idle(self, now: float | None = None) -> list[int]:
        current = self.now() if now is None else now
        expired: list[int] = []
        for chat_id, session in list(self.sessions.items()):
            if session.is_idle_expired(current):
                await session.stop(interrupt=False)
                self.sessions.pop(chat_id, None)
                expired.append(chat_id)
        return expired
