# Structured Container Logging Design

## Objective

Emit each Python log event, including a complete exception traceback, as one
single-line JSON document. Keep Docker as the local log transport and Azure
Monitor Agent as the remote shipper to `ContainerLogs_CL`.

Apply equivalent changes to both repositories:

- `C:\Users\Saturn\Desktop\lifeMg`
- `C:\Users\Saturn\Desktop\test3\lifeManagerOs`

## Application logging

Add a shared `telegram-bot/logging_config.py` module using only Python's
standard library. It configures the root logger with a JSON formatter that
emits timestamp, level, logger, message, optional event metadata, exception
type, and the complete formatted exception. `json.dumps` escapes traceback
newlines so one event remains one physical Docker record.

The formatter redacts Telegram bot tokens, bearer credentials, and common
authorization-header forms before output. `httpx` and `httpcore` have a
minimum level of `WARNING`; application loggers retain `INFO`.

Existing `logging.basicConfig` calls in `bot.py` and `sessions.py` are replaced
with the idempotent shared configuration. Non-JSON subprocess output remains
supported by the ingestion fallback.

## Azure ingestion

Extend `ContainerLogs_CL` with `Logger`, `Event`, `ExceptionType`, and
`Exception` string columns. Update the DCR transform to unwrap Docker's JSON
envelope, parse the nested application JSON, and map structured fields.

For legacy or non-JSON lines, retain the existing level extraction and store
the original line in `Message`. Continue dropping `DEBUG` before ingestion.
Also reject successful `httpx` Telegram `getUpdates` records as defense in
depth.

## Reliability and security

Logging failures must not interrupt message handling. Logs remain available
through `docker logs` and are rotated by Docker. No direct Azure log exporter
is added, avoiding application coupling and duplicate ingestion.

Any Telegram token already exposed in historical logs must be rotated
separately; this change prevents future exposure but cannot revoke old values.

## Verification

Automated tests prove that:

- an exception is emitted as exactly one physical line;
- decoding that JSON recovers the complete traceback;
- application `INFO` remains enabled;
- `httpx`/`httpcore` `INFO` is suppressed while warnings and errors remain;
- sensitive credential patterns are redacted;
- logging configuration is idempotent.

Run the Telegram bot test suite and Terraform formatting/validation in each
repository. After deployment, query `ContainerLogs_CL` to confirm structured
columns and zero successful `getUpdates` polling records.
