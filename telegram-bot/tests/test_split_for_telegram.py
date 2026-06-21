import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import bot  # noqa: E402

MAX = 4096


def test_short_text_single_chunk():
    assert bot.split_for_telegram("hello") == ["hello"]


def test_empty_text_single_chunk():
    assert bot.split_for_telegram("") == [""]


def test_exactly_max_is_single_chunk():
    text = "a" * MAX
    assert bot.split_for_telegram(text) == [text]


def test_multiline_splits_and_preserves_order():
    line = "x" * 2000
    text = "\n".join([line, line, line])  # ~6002 chars over 3 lines
    chunks = bot.split_for_telegram(text)
    assert len(chunks) >= 2
    assert all(len(c) <= MAX for c in chunks)
    # content + order preserved (chunk boundaries may drop a newline)
    assert "\n".join(chunks).replace("\n", "") == text.replace("\n", "")


def test_single_line_longer_than_max_is_hard_split():
    text = "y" * (MAX * 2 + 50)
    chunks = bot.split_for_telegram(text)
    assert all(len(c) <= MAX for c in chunks)
    assert "".join(chunks) == text  # single line → no newlines added
