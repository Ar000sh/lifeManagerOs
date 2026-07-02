# Phase A Review — Session Handoff

**Purpose of these sessions:** Aroosh is **reviewing and learning** the `lifeos-mcp`
Phase A code (a standalone Python MCP server that resolves the Notion workspace at runtime
from a map and exposes 5 tools). Goal is to *understand how the MCP works and how it plugs
into the bot* — explain as we go, teach the design, not just rush changes.

Start by reading `lifeos-mcp/REVIEW.md` (the guided review walkthrough). This file is the
"where we left off" note on top of it.

## Branch / state
- Branch: `feat/dynamic-skills` (local, **NOT pushed**, **NOT merged** to main — it carries
  all of Phase A + dynamic skills work).
- Run tests from `lifeos-mcp/`: `../telegram-bot/.venv/Scripts/python.exe -m pytest -q`
  (currently **62 passing**). HEAD: `01f1abe`.
- Commit mode (established consent): commit-per-task on this branch, local, **no push**.
  End commit messages with the `Co-Authored-By: Claude Opus 4.8` trailer.

## What we've already walked through (you can skim, not re-explain unless asked)
- `config.py`, `models.py`, the map idea (`tests/fixtures/maps.py` — FIXTURE_MAP vs ALT_MAP),
  function-roles (tasks/schedule/catalog), `resolver_areas.py` (`_anchor_id`, `resolve_sources`,
  `_resolve_group` discovery), `resolver_stale.py` (`reconcile_group` + blast-radius guard),
  the 5 tools, and `add_record` routing.

## Still NOT walked through (likely next, if Aroosh wants to continue the review)
- `notion_client.py` (the only file touching Notion's REST API; `extract_props`/`build_props`)
- `calendar_client.py` (Google Calendar wrapper, lazy imports)
- `resolver_schema.py` (`schema_for`/`prop`/`is_done` — the "column names don't matter" rules)
- `server.py` (FastMCP wiring) and how Phase B will plug it into the bot/skills

## Changes made during review (all on this branch, found while reviewing)
1. **Per-venture `source_label`** (`766aef8..3954365`): split the overloaded `area_label` into
   `area_label` (life area) + `source_label` (venture). Carried through get_today/get_week/
   query_records/add_record/resolve_named.
2. **add_record no-guess** (`aa2c4fe`): refuses to silently misfile — ambiguous/unknown
   destination → `{"created": false, "error": "ambiguous_destination"|"destination_not_found",
   "candidates":[...]}`.
3. **Reconcile-on-read B+D** (`85933d2`, `7d979b2`, `01f1abe`): `reconcile_due_groups` daily
   gate + reactive-404 self-heal wired into get_today/get_week; `reconnect_notion` now reachable.

Specs/plans for these are in `docs/superpowers/{specs,plans}/2026-06-2*` (gitignored scratch).
The durable build log is `.superpowers/sdd/progress.md`.

## Open decisions (parked, Aroosh's call)
- `add_record`/`query_records` running their OWN reconcile (opt-in; deferred — see the
  reconcile spec). Today they ride the shared daily cache.
- Whether `query_records` should get a warnings channel (currently a bare list; degrades silently).

## Known limitations noted but not fixed (from REVIEW.md §5 etc.)
- `build_props` doesn't handle Notion **relations** → `add_record` v1 won't link a uni task to
  its Module.
- Classic `/v1/databases` endpoint vs newer data-sources — decide at live validation.
- Row-level resilience (a single malformed Notion row could drop a source's remaining rows).
- Phase B (integrate into bot/skills + live Notion validation) NOT started.
