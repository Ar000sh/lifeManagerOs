import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import telemetry  # noqa: E402


def _enable_with_mocks(monkeypatch):
    monkeypatch.setattr(telemetry, "_enabled", True)
    monkeypatch.setattr(telemetry, "_messages", MagicMock())
    monkeypatch.setattr(telemetry, "_duration", MagicMock())
    monkeypatch.setattr(telemetry, "_tokens", MagicMock())
    monkeypatch.setattr(telemetry, "_cost", MagicMock())


def test_record_run_noop_when_disabled(monkeypatch):
    monkeypatch.setattr(telemetry, "_enabled", False)
    messages = MagicMock()
    monkeypatch.setattr(telemetry, "_messages", messages)
    telemetry.record_run("today", "ok", 1.0, usage=None)
    messages.add.assert_not_called()


def test_record_run_dispatch_with_full_usage(monkeypatch):
    _enable_with_mocks(monkeypatch)
    usage = SimpleNamespace(input_tokens=10, output_tokens=20, cost_usd=0.01)
    telemetry.record_run("today", "ok", 2.5, usage=usage)
    telemetry._messages.add.assert_called_once_with(1, {"skill": "today", "status": "ok"})
    telemetry._duration.record.assert_called_once_with(2.5, {"skill": "today", "status": "ok"})
    assert telemetry._tokens.record.call_count == 2
    telemetry._cost.record.assert_called_once_with(0.01, {"skill": "today", "status": "ok"})


def test_record_run_skips_missing_usage_fields(monkeypatch):
    _enable_with_mocks(monkeypatch)
    usage = SimpleNamespace(input_tokens=10, output_tokens=None, cost_usd=None)
    telemetry.record_run("week", "ok", 1.0, usage=usage)
    assert telemetry._tokens.record.call_count == 1
    telemetry._cost.record.assert_not_called()


def test_record_run_handles_none_usage(monkeypatch):
    _enable_with_mocks(monkeypatch)
    telemetry.record_run("chat", "error", 0.5, usage=None)
    telemetry._messages.add.assert_called_once()
    telemetry._tokens.record.assert_not_called()
    telemetry._cost.record.assert_not_called()


def test_record_run_swallows_instrument_errors(monkeypatch):
    _enable_with_mocks(monkeypatch)
    telemetry._messages.add.side_effect = RuntimeError("boom")
    telemetry.record_run("today", "ok", 1.0, usage=None)  # must not raise
