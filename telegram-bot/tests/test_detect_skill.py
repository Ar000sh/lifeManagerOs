import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from routing import detect_skill  # noqa: E402


def test_detect_known_commands():
    assert detect_skill("/today") == "today"
    assert detect_skill("/week something") == "week"
    assert detect_skill("/add buy milk") == "add"


def test_detect_unknown_command_is_other():
    assert detect_skill("/foobar") == "other"
    assert detect_skill("/") == "other"


def test_detect_plain_text_is_chat():
    assert detect_skill("hello there") == "chat"


def test_detect_is_case_and_space_tolerant():
    assert detect_skill("  /TODAY") == "today"


def test_detect_command_inline_not_only_at_start():
    # the new behavior: a /skill anywhere in the message still counts
    assert detect_skill("remind me to run /today please") == "today"
    assert detect_skill("hey can you do /add buy milk") == "add"


def test_detect_first_matching_skill_wins():
    assert detect_skill("/today and also /week") == "today"


def test_detect_slash_without_known_command_is_other():
    # tradeoff of contains-style detection: any slash with no known skill -> other
    assert detect_skill("what is 1/2 of that") == "other"
