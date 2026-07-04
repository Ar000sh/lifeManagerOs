# Structured Container Logging Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Store each Python exception as one queryable JSON record while suppressing successful Telegram polling and preserving local Docker logs.

**Architecture:** A standard-library JSON formatter writes one physical line per record to stdout. Docker retains it, while the Azure Monitor DCR parses nested JSON into structured `ContainerLogs_CL` columns with a legacy fallback.

**Tech Stack:** Python 3.12 standard library, pytest, Docker `json-file`, Terraform, Azure Monitor DCR/KQL.

## Global Constraints

- No direct Azure log exporter or third-party Python dependency.
- Preserve application `INFO`; suppress only `httpx` and `httpcore` below `WARNING`.
- Redact credentials before stdout.
- Preserve legacy/non-JSON ingestion.

---

### Task 1: Structured application logging

**Files:**
- Create: `telegram-bot/logging_config.py`
- Create: `telegram-bot/tests/test_logging_config.py`
- Modify: `telegram-bot/bot.py`
- Modify: `telegram-bot/sessions.py`

**Interfaces:**
- Produces: `configure_logging() -> None` and `JsonFormatter.format(record) -> str`.
- Consumes: Python `logging.LogRecord` instances and optional `event` metadata.

- [ ] Write tests for one-line exceptions, complete decoded traceback, redaction, logger levels, and idempotency.
- [ ] Run `pytest -q tests/test_logging_config.py`; expect failure because `logging_config` is absent.
- [ ] Implement the formatter using `json.dumps`, UTC ISO timestamps, `traceback.format_exception`, and an idempotent tagged handler.
- [ ] Replace duplicated `basicConfig` calls in `bot.py` and `sessions.py` with `configure_logging()`.
- [ ] Run the focused test and complete bot suite; expect all tests to pass.

### Task 2: Structured Azure ingestion

**Files:**
- Modify: `infra/monitoring.tf`
- Test: `telegram-bot/tests/test_logging_config.py`

**Interfaces:**
- Consumes: Docker JSON whose `log` field is application JSON or legacy text.
- Produces: structured log columns plus the existing raw fields.

- [ ] Add a failing static contract test for the new columns, nested JSON parsing, fallback, and `getUpdates` filter.
- [ ] Run the focused test; expect the DCR contract assertions to fail.
- [ ] Add the columns and update `transform_kql` with structured parsing and legacy fallback.
- [ ] Run focused tests, `terraform fmt -check`, and `terraform validate`; expect success.

### Task 3: Final verification

- [ ] Run `ruff check telegram-bot` and the full pytest suite.
- [ ] Inspect the diff for credentials and unrelated changes.
- [ ] After deployment, query `ContainerLogs_CL | where TimeGenerated > ago(1h) | where Message has '/getUpdates' | count`; expect zero.
