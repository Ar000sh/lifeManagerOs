"""Custom bot metrics -> Azure Application Insights (Plan 3).

A metrics-only OpenTelemetry pipeline. There is deliberately NO trace or log
exporter here: the bot's logs already flow into the ContainerLogs_CL table
(Plan 1), so shipping them again would duplicate data and cost.

The whole module is a no-op unless APPLICATIONINSIGHTS_CONNECTION_STRING is
set, so local runs and tests need no Azure access. Telemetry must never break
message handling: setup failures disable it, and record failures are swallowed.

Public interface:
    init_telemetry()      - call once at startup
    record_run(...)       - call once per handled message
    shutdown_telemetry()  - call once on clean shutdown (flushes)
"""
import logging
import os

logger = logging.getLogger("lifeos-bot.telemetry")

# Set by init_telemetry(); until then telemetry is disabled and every call no-ops.
_enabled = False
_provider = None
_messages = None
_duration = None
_tokens = None
_cost = None


def init_telemetry():
    """Wire the metrics-only OTel pipeline. Safe to call once at startup."""
    global _enabled, _provider, _messages, _duration, _tokens, _cost

    conn = os.environ.get("APPLICATIONINSIGHTS_CONNECTION_STRING", "").strip()
    if not conn:
        logger.info("telemetry disabled (no APPLICATIONINSIGHTS_CONNECTION_STRING)")
        _enabled = False
        return

    try:
        # Imported lazily so the module no-ops cleanly when the packages or the
        # connection string are absent (local dev, tests).
        from azure.monitor.opentelemetry.exporter import AzureMonitorMetricExporter
        from opentelemetry.sdk.metrics import MeterProvider
        from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader

        exporter = AzureMonitorMetricExporter(connection_string=conn)
        reader = PeriodicExportingMetricReader(exporter, export_interval_millis=60_000)
        _provider = MeterProvider(metric_readers=[reader])
        meter = _provider.get_meter("lifeos-bot")

        _messages = meter.create_counter("bot.messages.handled")
        _duration = meter.create_histogram("bot.agent.run.duration", unit="s")
        _tokens = meter.create_histogram("bot.claude.tokens")
        _cost = meter.create_histogram("bot.claude.cost_usd", unit="USD")

        _enabled = True
        logger.info("telemetry enabled (App Insights metrics)")
    except Exception:  # noqa: BLE001 - telemetry must never break startup
        logger.exception("telemetry setup failed; continuing without metrics")
        _enabled = False


def record_run(skill, status, duration_s, usage=None):
    """Record the metrics for one handled message. Never raises."""
    if not _enabled:
        return
    try:
        attrs = {"skill": skill, "status": status}
        _messages.add(1, attrs)
        _duration.record(duration_s, attrs)
        if usage is not None:
            if usage.input_tokens is not None:
                _tokens.record(usage.input_tokens, {**attrs, "direction": "input"})
            if usage.output_tokens is not None:
                _tokens.record(usage.output_tokens, {**attrs, "direction": "output"})
            if usage.cost_usd is not None:
                _cost.record(usage.cost_usd, attrs)
    except Exception:  # noqa: BLE001 - a telemetry bug must never break the bot
        logger.exception("record_run failed; dropping metrics for this message")


def shutdown_telemetry():
    """Flush remaining metrics on a clean shutdown. No-op when disabled."""
    if not _enabled or _provider is None:
        return
    try:
        _provider.shutdown()
    except Exception:  # noqa: BLE001
        logger.exception("telemetry shutdown failed")
