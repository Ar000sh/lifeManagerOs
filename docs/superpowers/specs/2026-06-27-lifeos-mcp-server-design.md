# lifeos MCP Server v1 — Design Spec

**Date:** 2026-06-27
**Status:** Approved (brainstorming) — pending implementation plan
**Scope:** The "live data plane" from `context/architecture.md`. Vault is a separate follow-up.

---

## Program context

`context/architecture.md` describes a three-layer product: **agent (brain)** + **live
data plane (our `lifeos` MCP server)** + **knowledge vault (durable understanding)**.
This spec covers **only the live data plane — the `lifeos` MCP server v1**. The vault
(`recall`/`remember`/`get_insights`) is deliberately deferred to its own brainstorm/spec;
the server is its foundation and the vault depends on it (the reliability rule: volatile
facts always fetched live, durable understanding in the vault).

This builds directly on the **dynamic-skills foundation** (`feat/dynamic-skills`): the
runtime-resolution behaviour that today lives in `context/resolver.md` (LLM-followed
markdown) + `context/lifeos.map.json` becomes **deterministic, tested Python code**.

---

## Goal

Turn the four markdown skills' fragile, agent-followed resolution + querying into a small
**Python MCP server** whose tools do the deterministic work and return clean structured
data. The agent keeps doing what it is good at — understanding the request, choosing
tools, and writing the response. Concretely, v1 delivers the three architecture goals at
once:

- **Determinism** — resolution + Notion/Calendar queries become real code with a pytest
  suite (markdown skills never had tests).
- **Reuse** — one toolbox serves the Telegram bot, interactive Claude Code, and Claude
  desktop (registered once as an MCP server).
- **Portability** — workspace-specific facts live only in the map; swapping the map runs
  the same tools against a different workspace (path to multi-user, project #4).

---

## Decisions (locked in brainstorming)

1. **Scope:** MCP server first; vault later (own spec).
2. **Integration approach:** standalone Python **FastMCP stdio** server in this repo,
   calling the **Notion REST API and Google Calendar API directly** (reusing the bot's
   existing `NOTION_TOKEN` and cached Google OAuth token). Registered as a *third* stdio
   server in `agent_runner.build_options()` and in project `.mcp.json`.
   - *Rejected B:* a plain Python library imported by `bot.py` — gives Claude Code /
     desktop nothing and isn't a callable tool.
   - *Rejected C:* a "meta" MCP that proxies the existing Notion/Google MCP servers —
     an extra hop for no benefit when the bot already holds the API tokens.
3. **Tool surface (v1):** `get_today`, `get_week`, `query_records` (read) + `add_record`,
   `create_event` (write). No `update`/`mark_done` yet.
4. **Calendar:** owned by the server. `get_today`/`get_week` return one unified payload
   incl. events; `create_event` writes to Google Calendar.
5. **Tool output:** structured JSON. The **agent/skill formats** the briefing (matches the
   three-layer model; keeps presentation flexible and bilingual).
6. **Data model:** generic **function-based roles** + **map-declared areas** (below).

---

## Data model — generic roles + map-declared areas

The model separates a database's **function** (what it does) from its **label** (what it
is about). The code knows only functions; all domain labels live in the map.

**Function roles (known to the code):**

- **`tasks`** — anything with a status + due date (assignments, venture to-dos, chores).
- **`schedule`** — anything time-blocked (work shifts, classes, appointments).
- **`catalog`** — a list of entities that tasks relate to (modules → courses; equally
  clients, products, properties).

**Structural primitive (known to the code):**

- **`group`** — a parent under which children are enumerated live, each child owning its
  own source(s). "Business root → ventures" is one group; another map could declare
  "Courses → each course". One level of grouping in v1 (nested groups deferred).

**Areas (declared in the map):** a named, labelled bundle of sources and/or a group.
"Business", "University", "Work", "Module" are **labels in the map, not concepts in the
code.** Briefing sections are rendered from each area's `label`/`emoji`, so a different
person's `get_today` renders *their* areas with no code change.

Each **source** carries its own **property-role schema** mapping function property-roles
(`title`, `status`, `due_date`, `exam_date`, `catalog_rel`, …) to that source's real
column names — so one `tasks` role spans sources with very different columns.

---

## `context/lifeos.map.json` — v1 shape

```jsonc
{
  "workspace_root": "<id>",
  "anchors": { "business_root": "<id>", "university_section": "<id>",
               "university_tasks_db": "<id>", "modules_db": "<id>",
               "work_schedule_db": "<id>" },

  "areas": {
    "ventures":   { "label": "Business", "emoji": "🚀",
                    "group": { "under": "business_root",
                               "child_sources": [ { "role": "tasks" } ] } },
    "university": { "label": "University", "emoji": "🎓",
                    "sources": [ { "anchor": "university_tasks_db", "role": "tasks" } ],
                    "catalog": { "anchor": "modules_db", "role": "catalog" } },
    "work":       { "label": "Work", "emoji": "💼",
                    "sources": [ { "anchor": "work_schedule_db", "role": "schedule" } ] }
  },

  "role_schemas": {
    "university_tasks_db": { "role": "tasks", "title": "Name", "status": "Status",
                             "priority": "Priority", "due_date": "Due Date",
                             "exam_date": "Exam Date", "catalog_rel": "Module",
                             "readonly": ["Module (Name)", "Semester Label"],
                             "status_values": { "done": "Done" } },
    "work_schedule_db":    { "role": "schedule", "title": "Name", "date": "Date",
                             "start": "Start Time", "end": "End Time",
                             "day": "Day", "recurring": "Recurring" },
    "modules_db":          { "role": "catalog", "title": "Name", "semester": "Semester" }
  },

  "resolved": {
    "groups": {
      "ventures": {
        "<notion_page_id>": { "label": "Laundromat Hannover", "role": "tasks",
                              "tasks_db": "<id>", "cached_at": "2026-06-27" }
      }
    },
    "tombstones": { "<notion_id>": { "reason": "archived|deleted",
                                     "label": "…", "seen_at": "2026-06-27" } },
    "ignored": [ "<id>" ]
  }
}
```

**Source of truth** = `anchors` + `areas` + `role_schemas`. **`resolved`** is a disposable,
self-healing cache. **Group children are keyed by stable Notion ID**, with `label` as a
mutable attribute (rename-safe — see Stale handling).

**`status_values.done` OR `done_when`:** a `tasks` source declares how "done" is detected
— either a status-select value (`status_values.done`) **or** a checkbox predicate
(`done_when: { property: "Completed", equals: true }`). The `tasks` role is not tied to a
status-select.

---

## Portability contract (explicit guarantee)

| In **code** (workspace-agnostic) | In **`lifeos.map.json`** (this workspace) |
|---|---|
| The function roles `tasks` / `schedule` / `catalog` and the `group` primitive | Which areas exist and their labels/emojis |
| "Aggregate every `tasks` source, due ≤ today, not done" | That `due_date` is the column `Due Date` (or `Fällig`) |
| Cache-first resolve, enumerate-on-miss, self-heal, write-back | Which businesses/sources exist (found live) |

- **Swap the map → the same tools run against a different workspace, no code change.**
- A **role absent from a map** (no businesses, no work schedule) yields an **empty
  section, never an error** — the same `get_today` works for a user with a different life
  shape.
- **Boundary of dynamic:** the code knows a fixed vocabulary of *functions*. A workspace
  built on entirely different functions would need a new role schema, not just a new map;
  that is out of scope for v1 and acceptable for any life-OS-shaped workspace.

---

## Shape coverage

The model represents these workspace shapes:

| # | Shape | Representation | v1 |
|---|---|---|---|
| 1 | Flat area, one source | `sources: [{anchor, role}]` | ✅ |
| 2 | Flat area, multiple sources | `sources` is a list | ✅ |
| 3 | Group, child owns one source | `group.child_sources: [{role}]` | ✅ |
| 4 | Group, child owns several sources | `child_sources` is a **list** (A) | ✅ |
| 5 | Catalog standing alone | `sources:[{role:"catalog"}]` / `area.catalog` | ✅ |
| 6 | Tasks relate to a catalog | task schema `catalog_rel` + area `catalog` | ✅ |
| 7 | "Done" is a checkbox | `done_when` predicate (C) | ✅ |
| 8 | Prop-role absent in a source | **absent = feature absent** (D) | ✅ |
| 9 | Recurring vs one-off schedule | optional `day`/`recurring` props | ✅ |
| 10 | Read-only/rollup columns | `readonly: [...]`, never written | ✅ |
| 11 | Renamed/other-language columns | `role_schemas` maps role → real name | ✅ |
| 12 | **Nested** group | recursive `group` | ⏸ **v2** (schema leaves room) |
| 13 | Top-level section matching no area | resolver `ask_then_remember` adds an area | ✅ |
| 14 | Area with no sources | skipped in aggregation | ✅ |

**Adopted refinements:** **A** list-valued `child_sources`; **C** `done_when` checkbox
predicate alongside `status_values.done`; **D** explicit rule that a missing prop-role
means the feature does not exist in that source (tools skip it silently).

**Deferred:** nested groups (#12) — schema is forward-compatible; v1 resolver enumerates
one group level.

---

## Architecture & components

```
lifeos-mcp/                    # new Python package (FastMCP stdio server)
  server.py                    # FastMCP app: registers tools, wires deps
  config.py                    # loads lifeos.map.json + env tokens
  resolver.py                  # resolver.md procedure, ported to code (pure functions)
  notion_client.py             # thin Notion REST wrapper (httpx + NOTION_TOKEN)
  calendar_client.py           # Google Calendar wrapper (reuses cached OAuth token)
  models.py                    # dataclasses for structured payloads
  tools/
    get_today.py
    get_week.py
    query_records.py
    add_record.py
    create_event.py
  tests/                       # pytest
```

Five independently testable layers:

1. **`config`** — reads `context/lifeos.map.json` + env; single source of IDs.
2. **`resolver`** — pure functions; the runtime-resolution procedure as code.
3. **`notion_client` / `calendar_client`** — narrow API wrappers; the only code that
   touches the network, so resolver + tools test against fakes.
4. **`tools/`** — the five MCP tools; compose resolver + clients; return structured JSON;
   no presentation.
5. **`server`** — FastMCP registration + dependency wiring; registered in
   `agent_runner.build_options()` and project `.mcp.json`.

---

## Resolver functions (code)

- `areas()` — iterate `areas`; for `group` areas enumerate children under the anchor
  (cache-first, write-back), each child becoming a labelled source.
- `sources(role)` — every source of a function role across all areas.
- `schema(source_id, prop_role)` — real column via `role_schemas`; missing role → `None`
  (feature absent, rule D); never assume a name.
- `is_done(record, source)` — via `status_values.done` or `done_when` (rule C).
- `resolve_on_miss(...)` / `write_back(...)` — self-heal + cache update (see Stale).
- Ambiguity → returns a structured `needs_disambiguation` signal (the agent asks; the
  answer is written back to the map — tools cannot prompt).

---

## Tool contracts

Inputs are role-based (never IDs/column names). Outputs are structured JSON.

**`get_today()`** — area-labelled unified payload:
```jsonc
{ "date": "2026-06-27",
  "areas": [ { "label": "Business",   "emoji": "🚀", "tasks": [ {...} ] },
             { "label": "University", "emoji": "🎓", "tasks": [ {...} ], "exams": [ {...} ] },
             { "label": "Work",       "emoji": "💼", "shift": {...}|null } ],
  "events": [ { "start": "…", "end": "…", "title": "…" } ],
  "warnings": [ "…" ] }
```
Tasks: every `tasks` source, due ≤ today and not done. Shift: every `schedule` source,
date == today. Events: Google Calendar, today. The skill renders one block per returned
area — add an area to the map and it appears with no skill edit.

**`get_week()`** — same shape over Mon–Sun (Europe/Berlin); items carry their day so the
agent groups. Business tasks also include those whose status = the source's `this_week`
value, if declared.

**`query_records(role, filters?)`** — flexible read for ad-hoc questions. `role` is a
function role; `filters` is a small mapped dict (`{status, due_before, area, …}`)
translated to real columns via `role_schemas`. Returns matching structured records.

**`add_record(role, fields, area?)`** — create a Notion row. Resolves the destination
(role + optional `area`/child label), maps `fields` → real columns, applies defaults
(status = start value; priority = Medium if absent), creates via Notion API. Returns
`{ created: true, id, url, destination }`. **Records only — never creates areas, DBs,
sections, or businesses (project #3).**

**`create_event(title, start, end?, notes?)`** — Google Calendar event, Europe/Berlin,
default 1h. Returns `{ created: true, id, link }`.

**Dates:** computed by the tool from an injectable clock in Europe/Berlin and stored
ISO-8601 — not parsed from LLM free text. The agent passes resolved ISO dates or simple
relative hints the tool normalizes.

---

## Stale-entry handling

**Key fact:** in Notion a page/database **ID is permanent** — rename and move do not
change it. A cached ID only stops resolving on **trash/delete** or **lost access**. Notion
returns the same `404 object_not_found` for "deleted" and "no access", so the rule keys on
**error class and blast radius**, not a single failed lookup.

| Scenario | API signal | ID valid? | Response |
|---|---|---|---|
| Renamed | fetches fine, new title | yes | Non-event (keyed by ID); update stored `label` on sync. |
| Moved (anchored source) | fetches fine, new parent | yes | Works as-is. |
| Moved out of group | fetches by ID, not under group | yes | Drop group membership; note it. |
| Archived / trashed | `archived`/`in_trash: true` | recoverable | **Tombstone**; drop from active; revive if it reappears. |
| Permanently deleted | `404` on direct fetch | no | Drop. Anchor → re-discover/ask; group child → drop. |
| Access revoked / disconnected | `404` or `401/403` | unknown | **Do not infer delete** — see guard. |
| Transient (5xx/network/429) | retryable error | probably | Retry/backoff; **never mutate cache.** |

**Adopted rules (i)–(v):**

- **(i)** Resolved group children keyed by **stable Notion ID**, with `label` as a mutable
  attribute → renames are non-events and re-enumeration re-matches by ID.
- **(ii)** Classify the error **before** mutating cache: transient → retry; auth /
  mass-failure → STOP + "reconnect Notion"; single 404 on a confirmed-connected workspace
  → genuine delete; archived flag → tombstone.
- **(iii)** **Blast-radius guard:** if more than one entry fails to resolve in a single
  run, assume connection/permission (not mass deletion) and bail to the reconnect path
  rather than pruning.
- **(iv)** **Tombstones** (alongside `ignored`): archived/deleted IDs are remembered so we
  neither re-probe each run nor resurrect them; an archived one may be revived on a later
  sync.
- **(v)** **Rename-safe re-enumeration:** match children by ID — present-with-new-title →
  update label; ID-absent-but-fetchable → moved out, drop membership; ID-absent-and-404 →
  deleted, drop.

---

## Error handling (tools)

- **Wrong/disconnected workspace:** `workspace_root`/all anchors empty on load → explicit
  tool error, never a silently empty briefing.
- **Partial failure in `get_today`/`get_week`:** one broken source → recorded in
  `warnings[]`; the rest still returns.
- **Ambiguity:** tool returns `needs_disambiguation`; the agent asks one question and
  writes the answer to the map.
- **Network/API errors:** wrapped by the client layer into clean tool errors; the agent
  retains raw Notion/Calendar MCP for fallback on novel one-offs.

---

## Impact on existing artifacts

- **`context/lifeos.map.json`** — migrated from the dynamic-skills shape
  (`task_roles` + `rules.businesses`, group children keyed by name) to the **`areas` +
  `role_schemas`** shape with group children keyed by **ID**. One-time migration.
- **`context/resolver.md`** — **retired**; logic moves into `lifeos-mcp/resolver.py`. A
  short pointer note may remain.
- **`/today`, `/week`, `/add` skills** — shrink to thin formatters: "call the
  `get_today`/`get_week`/`add_record` tool, then format the result using this template."
  No IDs, no column names, no resolution logic.
- **`/refresh-notion`** — stays as the interactive **map builder** (bootstrap/sync); must
  be updated to emit the new `areas`/`role_schemas` schema (incl. ID-keyed group children,
  `done_when` detection).
- **`telegram-bot/agent_runner.py`** — register the `lifeos` server as a third stdio MCP
  server in `build_options()`; add it to `allowed_tools`. Reuse `NOTION_TOKEN` and the
  Google OAuth token already in the environment.
- **Project `.mcp.json`** — add the `lifeos` server so interactive Claude Code gets the
  same tools.

---

## Testing

- **Unit (no network):** resolver functions against fake-map fixtures for shapes #1–11,
  #13–14; property lookup incl. missing prop-role (D); `is_done` via select **and**
  checkbox (C); multi-source group children (A); stale-handling rules (i)–(v) incl. the
  blast-radius guard and rename re-match.
- **Tool tests:** the five tools with a **fake Notion/Calendar client** — assert correct
  resolved targets, filters, and structured payloads; injectable clock for dates.
- **Map-swap test:** the same tools against a second, differently shaped fake map
  (different labels, columns, a checkbox-done source) → proves portability.
- **Live validation (manual, against the real Notion):** parity of `get_today`/`get_week`
  vs the current skills; `add_record`/`create_event` routing; new-venture auto-pickup;
  renamed-column still resolves; archived entry tombstoned, not mass-pruned.
- **Objective gate:** no Notion IDs or raw column names anywhere in `lifeos-mcp/` except
  via the map file.

---

## Out of scope (v1)

- **Vault** (`recall`/`remember`/`get_insights`) — its own brainstorm/spec.
- **Mutations beyond create** (`update_record`, `mark_done`, calendar move/delete).
- **Structure creation** (new businesses, DBs, sections, views) — project #3.
- **Nested groups** (shape #12) — v2; schema is forward-compatible.
- **Multi-user backend** — the map/schema are portable by design, but per-user storage and
  Telegram-ID keying are project #4.
