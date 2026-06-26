# Resolver — how skills find things in Notion

Every Life-OS skill resolves Notion targets through this procedure. **Skills never
contain Notion IDs or raw column names** — they ask for *roles* and *property roles*,
and this file turns those into live IDs/columns using `context/lifeos.map.json`.

## The map
`context/lifeos.map.json` has:
- `workspace_root` — discovery entry point (used only by `/refresh-notion`).
- `anchors` — stable landmark IDs (business_root, university_section,
  university_tasks_db, modules_db, work_schedule_db).
- `rules` — how to enumerate variable things (e.g. businesses under `business_root`).
- `task_roles` — which roles `/today` and `/week` aggregate as "tasks".
- `db_role_schemas` — per role, the map from property-role (`title`, `status`,
  `due_date`, …) to that DB's actual column name, plus `status_values`.
- `resolved` — write-back cache of already-discovered instances: `businesses` (pages
  that ARE a business, with their `tasks_db`) and `ignored` (an array of page-ID strings
  — `["<page_id>", …]` — for pages under an anchor already checked and found NOT to be a
  business, so they are not re-probed every run).

## Procedure

### 0. Load
Read `context/lifeos.map.json`. If it does not exist, STOP and run `/refresh-notion`
in bootstrap mode first, then continue.

### 1. Resolve a role's instances
- **Single-instance role** (e.g. `university_tasks`, `modules`, `schedule`): the DB ID
  is the matching anchor (`university_tasks_db`, `modules_db`, `work_schedule_db`).
- **Multi-instance role via a rule** (e.g. `business_tasks` under the `businesses` rule)
  — **reconcile every run** so newly added instances are picked up automatically:
  1. Enumerate the child pages under the rule's `under` anchor (one cheap list call).
     This is the authoritative current set of instances.
  2. For a child already in `resolved.businesses`, reuse its cached `tasks_db` — no extra
     call (deep task data still resolves from cache).
  3. For a child already in `resolved.ignored`, skip it — no extra call.
  4. For a genuinely new child (in neither list), probe it once: does it contain a
     database matching the rule's `tasks_db_role` (a `business_tasks`-shaped DB)?
     - Exactly one match → it's an instance: **write it back** into `resolved.businesses`
       as `{ "page", "tasks_db", "role", "cached_at": <today> }`.
     - No match (a notes/test page, e.g. `test`, `Goethe A1`) → append its page ID to
       `resolved.ignored` so it is not re-probed on later runs.
     - Multiple candidate DBs / unclear → ask-then-remember (§5), then record the answer.
  5. Drop any `resolved.businesses` / `resolved.ignored` entry whose page no longer
     appears under the anchor (deleted or moved away).

  Steady-state cost: one list call; only a brand-new page triggers a one-time probe.

### 2. Resolve a named instance (e.g. "Laundromat's tasks DB")
Check `resolved.businesses[name]` first. Miss → if the §1 reconcile already ran this
invocation, its enumeration is current, so the name genuinely isn't a business yet;
otherwise enumerate under the rule's anchor once, match the name (case-insensitive, allow
partial), write back, then use it.

### 3. Property lookup
Never hardcode a column. For role R and property-role P, use `db_role_schemas[R][P]`.
For status filters, use `db_role_schemas[R].status_values` (e.g. `done`, `this_week`).

### 4. Resolve-on-miss / self-heal
If a cached ID errors when actually used (moved / deleted / archived), delete that
`resolved` entry, redo step 1/2 for just that branch, update the map, and continue. Do
not fail the whole command for one bad branch.

### 5. Ambiguity → ask-then-remember
If resolution is ambiguous (e.g. two task-like DBs under one business, or a top-level
section matching no rule), ask the user ONE question to disambiguate, then write the
answer into the map (`resolved`, or a new `rules`/`anchors` entry as appropriate) so it
is never asked again.

### 6. Workspace safety
If `workspace_root` or an anchor resolves to empty/not-found on a fresh load (wrong or
disconnected Notion workspace), STOP and tell the user to reconnect Notion — never emit
an empty result silently.

## What skills say
- "Resolve all `task_roles` sources" → every business_tasks DB + university_tasks DB.
- "Filter by the `due_date` property of role R" → use `db_role_schemas[R].due_date`.
- "Resolve the `schedule` source" → `anchors.work_schedule_db` with the `schedule` schema.
