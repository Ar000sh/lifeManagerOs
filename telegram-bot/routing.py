"""
Message routing for the Life OS bot.

Looks at the raw text the user sent and decides *what kind* of message it is,
so the Telegram handler can stay a thin dispatcher. The decision is returned as
a `Route`:

  - "stop"                -> /stop: interrupt + close the live conversation
  - "chat"                -> /chat: start (or feed) a long 30-min session
  - "standalone_command"  -> bare /today, /week, /add: run one-shot, no session
  - "command_conversation"-> /today help me ...: run the command, then converse
  - "conversation"        -> plain text: an implicit 10-min live session

`detect_skill` is kept for the telemetry label ("which skill was this?").
"""

from dataclasses import dataclass
from typing import Literal

RouteKind = Literal[
    "stop",
    "chat",
    "standalone_command",
    "command_conversation",
    "conversation",
]

_KNOWN_SKILLS = {"today", "week", "add"}


@dataclass(frozen=True)
class Route:
    kind: RouteKind
    skill: str
    text: str
    command_text: str | None = None
    followup_text: str | None = None


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


def _slash_command_parts(text: str) -> tuple[str | None, str]:
    """Split "/today rest of text" into ("today", "rest of text").

    Returns (None, text) when the message does not start with a slash command.
    """
    stripped = text.strip()
    if not stripped.startswith("/"):
        return None, stripped
    first, _, rest = stripped.partition(" ")
    command = first[1:].lower()
    return command, rest.strip()


def classify_message(text: str) -> Route:
    stripped = text.strip()
    command, rest = _slash_command_parts(stripped)
    if command == "stop":
        return Route(kind="stop", skill="stop", text=stripped)
    if command == "chat":
        return Route(
            kind="chat",
            skill="chat",
            text=stripped,
            command_text="/chat",
            followup_text=rest or None,
        )
    if command in _KNOWN_SKILLS:
        command_text = f"/{command}"
        if not rest:
            return Route(
                kind="standalone_command",
                skill=command,
                text=stripped,
                command_text=command_text,
            )
        return Route(
            kind="command_conversation",
            skill=command,
            text=stripped,
            command_text=command_text,
            followup_text=rest,
        )
    return Route(
        kind="conversation",
        skill="chat",
        text=stripped,
        followup_text=stripped,
    )
