import io
import json
import logging
from pathlib import Path

from logging_config import JsonFormatter, configure_logging


def _render_record(message, *, exc_info=None):
    stream = io.StringIO()
    handler = logging.StreamHandler(stream)
    handler.setFormatter(JsonFormatter())
    logger = logging.getLogger("test.structured-logging")
    logger.handlers = [handler]
    logger.propagate = False
    logger.setLevel(logging.INFO)
    logger.error(message, exc_info=exc_info)
    return stream.getvalue()


def test_exception_is_one_json_line_with_complete_traceback():
    try:
        raise ValueError("broken value")
    except ValueError:
        output = _render_record("operation failed", exc_info=True)

    assert len(output.splitlines()) == 1
    record = json.loads(output)
    assert record["level"] == "ERROR"
    assert record["logger"] == "test.structured-logging"
    assert record["message"] == "operation failed"
    assert record["exception_type"] == "ValueError"
    assert "Traceback (most recent call last)" in record["exception"]
    assert "ValueError: broken value" in record["exception"]


def test_sensitive_values_are_redacted_before_output():
    output = _render_record(
        "POST https://api.telegram.org/bot123456789:ABC_def-123/getUpdates "
        "Authorization: Bearer very-secret-value"
    )

    assert "ABC_def-123" not in output
    assert "very-secret-value" not in output
    assert output.count("[REDACTED]") == 2


def test_configuration_is_idempotent_and_limits_noisy_http_loggers():
    root = logging.getLogger()
    original_handlers = root.handlers[:]
    original_level = root.level
    httpx_level = logging.getLogger("httpx").level
    httpcore_level = logging.getLogger("httpcore").level
    try:
        root.handlers = []
        configure_logging()
        configure_logging()

        configured = [
            handler
            for handler in root.handlers
            if getattr(handler, "_lifeos_json_handler", False)
        ]
        assert len(configured) == 1
        assert root.level == logging.INFO
        assert logging.getLogger("httpx").level == logging.WARNING
        assert logging.getLogger("httpcore").level == logging.WARNING
        assert not logging.getLogger("httpx").isEnabledFor(logging.INFO)
        assert logging.getLogger("httpx").isEnabledFor(logging.WARNING)
        assert logging.getLogger("lifeos-bot").getEffectiveLevel() == logging.INFO
    finally:
        root.handlers = original_handlers
        root.setLevel(original_level)
        logging.getLogger("httpx").setLevel(httpx_level)
        logging.getLogger("httpcore").setLevel(httpcore_level)


def test_azure_ingestion_contract_supports_structured_and_legacy_logs():
    terraform = (
        Path(__file__).parents[2] / "infra" / "monitoring.tf"
    ).read_text(encoding="utf-8")

    for column in ("Logger", "Event", "ExceptionType", "Exception"):
        assert f'{{ name = "{column}", type = "string" }}' in terraform

    assert "extend app = parse_json(DockerMessage)" in terraform
    assert 'split(DockerMessage, " | ")' in terraform
    assert 'Logger == "httpx"' in terraform
    assert 'Message has "/getUpdates"' in terraform
