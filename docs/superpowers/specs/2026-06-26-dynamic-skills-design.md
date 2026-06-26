# Dynamic Life-OS Skills — Design Spec

**Date:** 2026-06-26
**Status:** Approved (brainstorming) — pending implementation plan
**Scope:** Foundation project #1 of 4. See "Program context" below.

---

## Program context

The broader goal is a customizable, multi-user life-management assistant. It
decomposes into four independent projects, built in order:

1. **Dynamic / instruction-based skills** ← *this spec*. Skills discover the
   Notion workspace at runtime instead of using hardcoded IDs, so they work no
   matter how the tree is shaped.
2. **New organization skills** — brainstorming sessions, generating
   epics/stories/tasks for business & software work.
3. **Workspace provisioning / create-from-shapes** (reframed from "Notion
   templates") — creating *any* new structure within the workspace (businesses,
   databases, sections, views, whole sub-trees) from reusable stored shapes.
4. **Multi-user plugin / infra** — other users connect their own Notion +
   Google credentials; infrastructure is hosted centrally; per-user config keyed
   by Telegram ID.

This spec covers **only project #1**. It is deliberately designed so #3 and #4
build on it cleanly (portable map schema; anything created later is
auto-discovered).

---

## Problem

Today's skills (`/today`, `/add`, `/week`, `/refresh-notion`) hardcode Notion
page IDs and collection URLs (e.g. `/today` lists four business task DBs by ID).
`context/notion.md` is a hand-maintained map and `/refresh-notion` re-crawls a
*fixed list of known IDs*. Consequences:

- Any change to the workspace shape (new business, moved section, renamed
  column) breaks skills or requires editing them.
- The skills cannot work against any other workspace, blocking multi-user.

**Goal:** skills contain **no Notion IDs and no raw column names**. They resolve
everything at runtime through a cached, self-healing map.

---

## Core model: roles + anchors, not a flat list of IDs

Two layers:

- **Anchors** — the few *stable landmarks* that get pinned to IDs. They almost
  never move.
- **Roles + enumeration rules** — the *variable* stuff (individual businesses,
  their task DBs) is found live by enumerating children under an anchor and
  matching a role. Adding a new business needs **zero** config change.

Every operational database has a **role** (`tasks`, `schedule`, `modules`, …). A
role can have **many** instances. This generalizes "what is a task": `/today`
means "aggregate every DB with role `tasks`, filtered to due-today," instead of
"these four hardcoded DBs."

Because columns can be named anything, each resolved DB also stores a
**property-role schema** mapping role properties (`title`, `status`, `due_date`,
`priority`, …) to that DB's actual column names. This is what makes it work "no
matter how it looks" (e.g. a `due_date` column named `Deadline` or `Fällig`).

---

## Component 1 — `context/lifeos.map.json`

The machine-readable map that replaces all hardcoded IDs. `context/notion.md`
becomes a human-readable summary **regenerated from this file** so it never
drifts.

Four parts:

**a) Anchors** (the only pinned IDs):
```json
"anchors": {
  "business_root":       "02b35e4e-...",
  "university_section":  "25a31bbe-...",
  "university_tasks_db": "580c2d1d-...",
  "modules_db":          "5e62acec-...",
  "work_schedule_db":    "55f90404-..."
}
```

**b) Enumeration rules** (how to find the variable stuff live):
```json
"rules": {
  "businesses": {
    "under": "business_root",
    "each_child_is": "a business page",
    "tasks_db_role": "tasks"
  }
}
```

**c) Roles + property-role schemas**:
```json
"db_role_schemas": {
  "tasks":    { "title": "Name", "status": "Status",
                "due_date": "Due Date", "priority": "Priority" },
  "schedule": { "title": "Name", "date": "Date",
                "start": "Start Time", "end": "End Time" }
}
```

**d) Resolution cache (write-back, disposable, self-healing)**:
```json
"resolved": {
  "businesses": {
    "Laundromat Hannover": { "page": "39b5...", "tasks_db": "fdffad80-...", "cached_at": "2026-06-26" },
    "Van Company Czech Republic": { "page": "b539...", "tasks_db": "ae28...", "cached_at": "2026-06-26" }
  }
}
```

**Source of truth** = anchors + rules + role-schemas. **`resolved`** is a
disposable cache filled lazily as skills touch things.

### Token-cost rationale

"Lean" does **not** mean re-discover everything every run. Discovery happens
**once per thing, ever**, then is cached:

| Operation | Discovery cost |
|---|---|
| Add a task to an existing business (steady state) | **Zero** (ID cached) |
| First time touching a new business | One cheap enumeration, then cached |
| `/today` | One cheap list call to reconcile businesses under `business_root` (auto-pickup of new ones), then only the data queries it would run anyway |

We never deep-crawl the workspace per run. We crawl once at setup / manual
refresh, cache resolved IDs lazily, and operate from cache after. Per-operation
cost ≈ identical to today's hardcoded skills.

---

## Component 2 — `context/resolver.md` (shared procedure)

One documented procedure every skill references, so skills never re-implement
discovery. A skill **never contains a Notion ID or a column name** — it only
says "give me every `tasks` source" or "filter by the `due_date` property."

Procedure:

1. **Load** `lifeos.map.json`. Missing → run setup/mapping (Component 4).
2. **Need a role instance:**
   - Single-instance role → use the matching anchor.
   - Multi-instance role (a rule) → **reconcile every run**: enumerate the anchor's
     children once (one cheap list call); reuse `resolved.businesses` for known ones;
     probe only genuinely-new pages (classify as a business via a `business_tasks`-shaped
     DB, else record in `resolved.ignored` to avoid re-probing); drop vanished entries;
     **write back** new findings. This makes new businesses auto-appear without a manual
     refresh.
3. **Resolve-on-miss / self-heal:** if a cached ID errors in use (moved /
   deleted / archived), drop that entry, re-resolve just that branch, update the
   map.
4. **Property access** always goes through `db_role_schemas` — never assume a
   column name.

**Ambiguity handling (ask-then-remember):** when the resolver can't confidently
resolve something (two task-like DBs under one business; a new top-level section
matching no rule), it asks one quick question and **writes the answer into the
map** so it's never asked again.

**Portability:** swapping the local `lifeos.map.json` for a per-Telegram-ID
record makes the exact same skills work for another user — no skill edits
(enables project #4).

---

## Component 3 — Reworked skills

Each skill loses its hardcoded IDs and gains: *"Resolve targets via
`context/resolver.md`."*

**`/refresh-notion` → mapper / setup skill (biggest change).**
- Discover anchors from the workspace root (Business / University / Work
  sections; task / schedule / module DBs).
- Infer each DB's role and property-role schema from name + property types;
  confirm ambiguities (ask-then-remember).
- Write `lifeos.map.json` + regenerate `notion.md`.
- Later runs are incremental: re-verify anchors, refresh role-schemas, report
  changes. Also the entry point when no map exists (bootstrap).

**`/today`.**
- Resolve **all `tasks` sources** (university + every business under
  `business_root`); query each filtered to due-today / overdue / this-week via
  mapped `due_date`/`status`.
- Resolve the `schedule` source for today's shift; pull Calendar as now.
- New businesses appear automatically.

**`/add`** (record creation — rows, not structures).
- Routing concept unchanged (task→tasks, shift→schedule, event→calendar), but
  the destination is a resolved role/instance, not a baked-in URL.
- "Task for \<business\>" resolves that business under `business_root`.
- Creation uses the resolved DB's property-role schema to set the right columns.
- **Out of scope:** creating new *structures* (new business pages, DBs,
  sections, views) — deferred to project #3. Creating *records* into existing
  destinations is fully in scope (no capability lost).

**`/week`.**
- Same treatment as `/today` over a 7-day window across all resolved roles.
  (Match current behavior, swap in the resolver.)

**Records vs structures (the scope line):** this project creates *records*
(tasks, shifts, modules, events). Creating *structures* that change the shape of
the workspace is the broadened project #3. Anything created later is
auto-discovered by the resolver, so it works with these skills without edits.

---

## Component 4 — Setup, bootstrap & error handling

**Bootstrap:** when a skill finds no `lifeos.map.json`, it triggers
`/refresh-notion` in bootstrap mode (discover from root, infer roles, confirm
ambiguities, write map). For Aroosh's first run, seed directly from the existing
`context/notion.md` (real IDs already known) — day one is instant, not a cold
crawl.

**Error / edge handling (defined in the resolver):**
- **No / wrong workspace connected** (the "third workspace" gotcha): if root or
  anchors return empty, stop and tell the user to reconnect Notion — never
  silently emit an empty `/today`.
- **Anchor moved/deleted:** resolve-on-miss re-discovers; if truly gone, ask.
- **Ambiguous / unmapped:** ask-then-remember.
- **Stale cache entry:** dropped and re-resolved for just that branch.
- **Partial failure in `/today`:** report the rest, flag the broken source,
  don't fail the whole briefing.

---

## Validation

Instruction-based skills + a JSON map → "testing" = running each skill against
the real workspace plus deliberately broken setups.

**Correctness (parity with today):**
- `/today` and `/week` produce the same results via the resolver as the current
  hardcoded versions.
- `/add` routes a task, exam, shift, module, and calendar event to the right
  resolved destinations.

**Dynamic behavior:**
- **New business:** add a dummy business page + tasks DB → `/today` picks it up
  with zero skill/map edits (auto-enumeration).
- **Renamed column:** rename a task DB's `Due Date` → after refresh, `/today`
  still filters correctly via the property-role schema.
- **Moved anchor:** move a section → resolve-on-miss self-heals the map.
- **Ambiguity:** two task-like DBs under one business → resolver asks once,
  remembers.

**Safety:**
- Disconnect / wrong workspace → skills stop and prompt to reconnect, no empty
  briefing.

**Objective pass/fail:** grep the four skills — they contain **no Notion IDs and
no raw column names**.

---

## Out of scope (this project)

- Creating new *structures* (businesses, DBs, sections, views) — project #3.
- New organization skills (brainstorming, story/epic generation) — project #2.
- Multi-user cloud store keyed by Telegram ID — project #4 (schema is designed
  to be portable, but the backend is not built here).
