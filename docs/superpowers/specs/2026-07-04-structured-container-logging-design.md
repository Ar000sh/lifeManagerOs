# Structured Container Logging Design

## Objective

Emit each Python log event, including a complete exception traceback, as one single-line JSON document. Keep Docker as the local log transport and Azure Monitor Agent as the remote shipper to `ContainerLogs_CL`.

## Application logging

Add `telegram-bot/logging_config.py` using Python's standard library. Emit timestamp, level, logger, message, optional event metadata, exception type, and complete exception. JSON encoding escapes traceback newlines, keeping one event in one Docker record. Redact Telegram tokens and authorization credentials. Keep application loggers at `INFO`; set `httpx` and `httpcore` to `WARNING`.

## Azure ingestion

Extend `ContainerLogs_CL` with `Logger`, `Event`, `ExceptionType`, and `Exception`. Parse nested application JSON in the DCR while retaining legacy text fallback. Continue dropping `DEBUG` and successful Telegram `getUpdates` records before ingestion.

## Verification

Tests prove one-line exception output, complete decoded traceback, logger levels, credential redaction, and idempotent configuration. Run the full bot suite plus Terraform formatting and validation.
