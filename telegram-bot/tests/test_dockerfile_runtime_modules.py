from pathlib import Path


def test_dockerfile_copies_runtime_telemetry_module():
    dockerfile = Path(__file__).resolve().parents[2] / "Dockerfile"
    content = dockerfile.read_text(encoding="utf-8")

    assert "COPY telegram-bot/telemetry.py ./telemetry.py" in content
