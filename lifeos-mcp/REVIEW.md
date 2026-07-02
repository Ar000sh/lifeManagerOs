# Phase A Review Guide — `lifeos` MCP server

A step-by-step plan for reviewing the Phase A code before we integrate it into the
live bot/skills (Phase B). Work top to bottom; tick the boxes as you go. Nothing here
touches your live Notion — it's all reading + running the offline test suite.

> Spec: `docs/superpowers/specs/2026-06-27-lifeos-mcp-server-design.md`
> Plan: `docs/superpowers/plans/2026-06-27-lifeos-mcp-server.md`
> Full build log (every task, reviewer, fix): `.superpowers/sdd/progress.md`

---

## 0. What you're reviewing (1 minute)

Phase A is a **standalone Python MCP server** (`lifeos-mcp/`). Its job: resolve your
Notion workspace at runtime from `context/lifeos.map.json` and expose five tools
(`get_today`, `get_week`, `query_records`, `add_record`, `create_event`) that return
clean structured data. It does **not** yet plug into the bot or skills — that's Phase B.
So right now you're reviewing a self-contained library + its tests. If it's wrong, your
daily `/today` etc. are unaffected (they still use the old markdown skills).

The point of the review: **do you trust this code, and do you agree with its design
decisions, before we wire it into the thing you use every day?**

---

## 1. Run the tests first (2 minutes)

From the repo root:

```bash
cd lifeos-mcp
../telegram-bot/.venv/Scripts/python.exe -m pytest -v
```

- [ ] You see **39 passed**, no failures, no warnings.
- [ ] Skim the test names — they read like a behavior spec (e.g.
  `test_blast_radius_guard_preserves_moved_out_entry`,
  `test_today_calendar_window_uses_berlin_offset`).

Green tests mean the behavior is *locked*. Your job below is to check the behavior is
the **right** behavior, not just that it's consistent.

---

## 2. Understand the architecture (5 minutes)

Three ideas hold the whole thing together. Make sure these click before reading files:

1. **Function-roles, not life-labels.** The code only knows `tasks`, `schedule`,
   `catalog`. "Business", "University", "Module" are **labels in the map**, not concepts
   in code. This is what makes it portable to a different workspace.
2. **The map is the only place IDs live.** `anchors` pin the stable landmarks;
   `role_schemas` map function-properties (`due_date`) to real column names
   (`"Due Date"` / `"Fällig"`); `resolved` is a self-healing cache of discovered
   businesses. Code never hardcodes an ID or a column name.
3. **Tools return data; the agent formats.** A tool gives back structured JSON; the
   presentation (the 🚀🎓💼 briefing) is the agent's job, later.

Quick way to *see* the two shapes the code must handle:
- [ ] Open `tests/fixtures/maps.py`. Compare `FIXTURE_MAP` (your shape) with `ALT_MAP`
  (a fictional user: labels "Clients"/"Persönlich", German columns, a checkbox for
  "done"). The same tools must work on both. That contrast is the core design idea.

---

## 3. Read the code in this order

For each file: read it, then answer the **Check** questions. If a check fails or feels
wrong, note it — that's review gold.

### 3a. `lifeos_mcp/config.py` (easy warm-up)
Loads/saves the map JSON and reads env settings.
- [ ] **Check:** map is read/written UTF-8 and pretty-printed (so the file stays
  human-diffable in git)?
- [ ] **Check:** the env keys it reads (`NOTION_TOKEN`, `LIFEOS_MAP_PATH`, Google ones)
  match what the bot already provides?

### 3b. `lifeos_mcp/models.py` (data shapes)
The dataclasses every tool returns; each has `to_dict()` for JSON.
- [ ] **Check:** dates serialize as ISO strings (`YYYY-MM-DD`) or `None` — nothing that
  can't be turned into JSON.

### 3c. `lifeos_mcp/resolver_schema.py` (the "no matter how it looks" logic)
`schema_for`, `prop`, `is_done` — the rules that make column names not matter.
- [ ] **Check (rule D):** `prop(schema, "thing_not_in_schema")` returns `None`, never
  crashes. (A missing property just means "this source doesn't have that field".)
- [ ] **Check (rule C):** `is_done` works two ways — a status *select* equal to the
  "done" value, **or** a *checkbox* (`done_when`). This is why `ALT_MAP`'s German
  checkbox-done works.

### 3d. `lifeos_mcp/resolver_areas.py` (the heart — read carefully)
Turns areas + the businesses rule into live source IDs; enumerates businesses once and
caches them.
- [ ] **Check:** on a **cache hit** (`resolved.groups.ventures` already populated) it does
  **no** network enumeration — it just uses the cached `tasks_db` ids. (This is the
  token-cost promise: discovery happens once, ever.)
- [ ] **Check:** on a **cache miss** it enumerates children under the anchor, finds each
  one's tasks DB, and **writes them back** keyed by the Notion **page id** (not the
  name). Keying by id is what makes renames harmless.
- [ ] **Check:** an anchored source (e.g. University) looks up its schema by the anchor
  **name**, while a discovered business uses `child_schema_defaults`. (Ids stay only in
  `anchors`.)

### 3e. `lifeos_mcp/resolver_stale.py` (the safety logic — the file you opened)
What happens when a cached id stops resolving. This is the subtle one; a review here
already caught a real bug.
- [ ] **Check (the big one):** the **blast-radius guard**. If **more than one** child
  fails to resolve in a run, it raises `WorkspaceUnavailable` and **mutates nothing** —
  drops, tombstones, AND the moved-out removals are all deferred until *after* the guard.
  (The original code popped moved-out entries *before* the guard — that leak is fixed;
  `test_blast_radius_guard_preserves_moved_out_entry` proves it.)
- [ ] **Check:** a renamed page (same id, new title) just updates the stored `label` — it
  is **not** treated as deleted.
- [ ] **Check:** a single genuine `404` (deleted) is tombstoned so it isn't re-probed,
  but a *permissions* failure (which Notion also returns as 404) can't masquerade as a
  mass deletion because of the blast-radius guard.

### 3f. `lifeos_mcp/notion_client.py` (the API wrapper)
The only file that talks to Notion's REST API, plus `extract_props`/`build_props`.
- [ ] **Check:** HTTP status mapping — 404→NotFound, 401/403→Auth, 429/5xx→Transient.
  (These feed the stale logic above.)
- [ ] **Check / decide:** it targets the **classic** `/v1/databases/{id}/query` endpoint.
  If your live workspace needs Notion's newer "data sources" endpoints, only this file
  changes. (Flagged for Phase B live test.)
- [ ] **Known limitation:** `build_props` picks the Notion field type from the role
  *name*. It covers v1's roles (title/status/priority/dates/text) but a *relation* (like
  linking a task to a Module) isn't handled — `add_record` v1 won't set the module
  relation. Decide if that matters for v1.

### 3g. `lifeos_mcp/calendar_client.py`
Google Calendar wrapper; Google libs imported lazily so the module loads without them.
- [ ] **Check:** only `normalize_event` is unit-tested (pure). The Google calls are thin.
- [ ] **Phase-B watch:** it relies on the cached OAuth token self-refreshing — we verify
  that live in Task 20.

### 3h. `lifeos_mcp/tools/*.py` (what the agent will call)
- [ ] **`get_today.py` — Check:** the calendar window is built in **Europe/Berlin**
  (`_day_window`), not UTC. (A review caught this as a real bug; `tzdata` was added so it
  works on Windows too.)
- [ ] **`get_today.py` / `get_week.py` — Check:** if one source errors, it's recorded in
  `warnings` and the rest of the briefing still returns (no all-or-nothing failure).
- [ ] **`add_record.py` — Check:** destination routing — a business *name* ("Laundromat")
  resolves the right tasks DB, an area *label* ("University") resolves the anchored
  source, and it **never creates** databases/sections (records only).
- [ ] **`query_records.py` — Check:** filters (status/area/due_before/after/not_done) map
  through the schema, no hardcoded columns.

### 3i. `lifeos_mcp/server.py` (the MCP wiring)
- [ ] **Check:** exactly five tools, named `get_today`/`get_week`/`query_records`/
  `add_record`/`create_event`.
- [ ] **Check:** every tool **saves the map** after running (so newly-discovered
  businesses persist), and `get_today`/`get_week` return `{"error": "reconnect_notion"}`
  instead of an empty briefing when the workspace looks disconnected.

---

## 4. The portability proof (3 minutes — the payoff)

- [ ] Read `tests/test_portability.py`. It runs `get_today` against `ALT_MAP` and asserts
  a German-column task shows up, a checkbox-done task is filtered out, and the
  map-driven label "Persönlich" appears — **all with the same tool code**.
- [ ] Convince yourself: this is the whole thesis — *swap the map, the tools just work*.
  If you believe this test, you believe the design.

---

## 5. Decisions I need from you (the follow-ups)

These are tracked but **not** acted on. Tell me your call on each:

- [ ] **Row-level resilience (Medium):** per-*source* isolation works, but a single
  malformed Notion row could drop that source's remaining rows. Low likelihood (Notion
  returns typed data). **Fix now, or accept for v1?**
- [ ] **Module relation in `add_record` (design debt):** v1 won't link a university task
  to its Module. **Needed for v1, or fine to defer?**
- [ ] **Notion endpoint:** classic `/v1/databases` vs newer data-sources — we'll know
  which your workspace needs at live validation. (No action now.)

---

## 6. Optional: watch a tool run without Notion (5 minutes)

If you want to *see* a tool work against fake data (no network), run:

```bash
cd lifeos-mcp
../telegram-bot/.venv/Scripts/python.exe -c "import copy, json; from datetime import date; from tests.fixtures.maps import FIXTURE_MAP; from tests.fakes import FakeNotionClient, FakeCalendarClient; from lifeos_mcp.tools.get_today import get_today; p=get_today(copy.deepcopy(FIXTURE_MAP), FakeNotionClient(), FakeCalendarClient(), date(2026,6,27)); print(json.dumps(p.to_dict(), indent=2, ensure_ascii=False))"
```

- [ ] You get a structured `TodayPayload` JSON with `areas`, `events`, `warnings` —
  the exact shape the agent will format into a briefing.

---

## 7. Sign-off

When you're done, tell me one of:
- **"Phase A looks good — proceed to Phase B"**, or
- **"Change X first"** (anything from §3 checks or §5 decisions), or
- **"Run the final whole-branch review"** if you want a fresh multi-aspect pass over all
  of Phase A before integrating.

Phase B will then: fix the Task 17 wording → migrate your real `lifeos.map.json` →
register the server in the bot + `.mcp.json` → thin `/today` `/week` `/add` onto the
tools. Live validation (Task 20) stays with you, since it needs your real Notion.
