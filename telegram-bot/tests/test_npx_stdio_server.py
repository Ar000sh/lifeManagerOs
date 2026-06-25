import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import agent_runner  # noqa: E402


def test_linux_uses_npx(monkeypatch):
    monkeypatch.setattr(agent_runner.sys, "platform", "linux")
    cfg = agent_runner._npx_stdio_server("some-pkg", {"K": "V"})
    assert cfg == {
        "type": "stdio",
        "command": "npx",
        "args": ["-y", "some-pkg"],
        "env": {"K": "V"},
    }


def test_windows_uses_cmd(monkeypatch):
    monkeypatch.setattr(agent_runner.sys, "platform", "win32")
    cfg = agent_runner._npx_stdio_server("some-pkg", {})
    assert cfg["command"] == "cmd"
    assert cfg["args"] == ["/c", "npx", "-y", "some-pkg"]
