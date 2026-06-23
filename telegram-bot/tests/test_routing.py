import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from routing import classify_message, detect_skill  # noqa: E402


def test_stop_route():
    route = classify_message("/stop")
    assert route.kind == "stop"
    assert route.skill == "stop"


def test_chat_route_without_text():
    route = classify_message("/chat")
    assert route.kind == "chat"
    assert route.skill == "chat"
    assert route.followup_text is None


def test_chat_route_with_text():
    route = classify_message("/chat help me decide")
    assert route.kind == "chat"
    assert route.skill == "chat"
    assert route.followup_text == "help me decide"


def test_standalone_command_route():
    route = classify_message("/today")
    assert route.kind == "standalone_command"
    assert route.skill == "today"
    assert route.command_text == "/today"


def test_command_plus_conversation_route():
    route = classify_message("/today help me prioritize")
    assert route.kind == "command_conversation"
    assert route.skill == "today"
    assert route.command_text == "/today"
    assert route.followup_text == "help me prioritize"


def test_normal_text_route():
    route = classify_message("what should I do now?")
    assert route.kind == "conversation"
    assert route.skill == "chat"
    assert route.followup_text == "what should I do now?"


def test_detect_skill_for_embedded_known_command():
    assert detect_skill("please run /week") == "week"
