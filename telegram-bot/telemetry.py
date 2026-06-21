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
    if not _enabled:
        logger.error("Metric recording failed due to telemetry setup failure")
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
    if not _enabled or _provider is None:
        logger.error("Metric Shutdown nothing to shutdown due telemetry setup failure")
        return
    try:
        _provider.shutdown()
    except Exception:
        logger.exception("telemetry shutdown failed")
