from pathlib import Path

import pytest

# Every local .py module the bot imports at runtime must be COPYed into the
# image individually (the Dockerfile copies files one-by-one, not the whole
# folder). A module that runs fine locally but is missing here crashes the
# container at import time — something the unit tests can't catch.
RUNTIME_MODULES = [
    "bot.py",
    "telemetry.py",
    "agent_runner.py",
    "routing.py",
    "sessions.py",
]


@pytest.mark.parametrize("module", RUNTIME_MODULES)
def test_dockerfile_copies_runtime_module(module):
    dockerfile = Path(__file__).resolve().parents[2] / "Dockerfile"
    content = dockerfile.read_text(encoding="utf-8")

    assert f"COPY telegram-bot/{module} ./{module}" in content
