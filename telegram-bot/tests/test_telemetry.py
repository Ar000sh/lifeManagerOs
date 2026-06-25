import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, call

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
    telemetry._tokens.record.assert_has_calls([
        call(10, {"skill": "today", "status": "ok", "direction": "input"}),
        call(20, {"skill": "today", "status": "ok", "direction": "output"}),
    ], any_order=False)
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
    telemetry._messages.add.assert_called_once()  # confirm we reached the throw point before swallowing


def test_record_run_includes_session_attributes(monkeypatch):
    monkeypatch.setattr(telemetry, "_enabled", True)
    monkeypatch.setattr(telemetry, "_messages", MagicMock())
    monkeypatch.setattr(telemetry, "_duration", MagicMock())
    monkeypatch.setattr(telemetry, "_tokens", MagicMock())
    monkeypatch.setattr(telemetry, "_cost", MagicMock())

    telemetry.record_run(
        "chat",
        "ok",
        1.5,
        usage=None,
        session_mode="implicit",
        session_event="created",
    )

    expected_attrs = {
        "skill": "chat",
        "status": "ok",
        "session_mode": "implicit",
        "session_event": "created",
    }
    telemetry._messages.add.assert_called_once_with(1, expected_attrs)
    telemetry._duration.record.assert_called_once_with(1.5, expected_attrs)


def test_init_disabled_without_connection_string(monkeypatch):
    monkeypatch.delenv("APPLICATIONINSIGHTS_CONNECTION_STRING", raising=False)
    monkeypatch.setattr(telemetry, "_enabled", True)  # prove init flips it to False
    telemetry.init_telemetry()
    assert telemetry._enabled is False


def test_init_enabled_creates_instruments(monkeypatch):
    monkeypatch.setenv("APPLICATIONINSIGHTS_CONNECTION_STRING",
                       "InstrumentationKey=00000000-0000-0000-0000-000000000000")
    monkeypatch.setattr(telemetry, "_enabled", False)
    telemetry.init_telemetry()
    assert telemetry._enabled is True
    assert telemetry._messages is not None
    assert telemetry._duration is not None
    assert telemetry._tokens is not None
    assert telemetry._cost is not None
    telemetry.shutdown_telemetry()
