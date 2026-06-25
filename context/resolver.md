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
- `resolved` — write-back cache of already-discovered instances.

## Procedure

### 0. Load
Read `context/lifeos.map.json`. If it does not exist, STOP and run `/refresh-notion`
in bootstrap mode first, then continue.

### 1. Resolve a role's instances
- **Single-instance role** (e.g. `university_tasks`, `modules`, `schedule`): the DB ID
  is the matching anchor (`university_tasks_db`, `modules_db`, `work_schedule_db`).
- **Multi-instance role via a rule** (e.g. `business_tasks` under the `businesses` rule):
  1. If `resolved.businesses` is non-empty, use those `tasks_db` IDs (cache hit — no
     discovery).
  2. On a cache miss or when you need to confirm freshness, enumerate child pages under
     the rule's `under` anchor (one call), find each child's tasks database, and
     **write each back** into `resolved.businesses` as
     `{ "page", "tasks_db", "role", "cached_at": <today> }`.

### 2. Resolve a named instance (e.g. "Laundromat's tasks DB")
Check `resolved.businesses[name]` first. Miss → enumerate under the rule's anchor, match
the name (case-insensitive, allow partial), write back, then use it.

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
