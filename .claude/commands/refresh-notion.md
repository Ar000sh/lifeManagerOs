# /refresh-notion — Build & sync the workspace map

Build or repair the Life-OS **map** for the current identity, written to
`context/maps/<LIFEOS_IDENTITY>.json` (default identity: the single configured chat id).
Then regenerate the human-readable `context/notion.md`. This is the only skill that writes
the durable map; the running `lifeos` MCP server only reads it. After writing locally, push
it to the store with:
`python -m lifeos_mcp.mapctl push --identity <id> --file context/maps/<id>.json`.

The map shape is authoritative and typed. Top-level keys:
`workspace_root, anchors, areas, role_schemas, child_schema_defaults, resolved`.

## Mode A — Bootstrap (no map yet, or `--bootstrap`)
1. Find the workspace root (`workspace_root` if present, else `notion-search` the Life-OS
   root page). If nothing is found, STOP and ask the user to (re)connect Notion.
2. Discover top-level **areas** and pin **anchors** (stable landmark ids), e.g.
   `business_root`, `university_tasks_db`, `modules_db`, `work_schedule_db`. Ask ONE
   question when a candidate is ambiguous (ask-then-remember).
3. Build `areas`: each area has a `label`, `emoji`, and one of:
   - `sources`: `[{ "anchor": "<name>", "role": "tasks|schedule" }]` for anchored DBs,
   - `group`: `{ "under": "<anchor>", "child_sources": [{"role": "tasks"}] }` for
     child-enumerated ventures,
   - `catalog`: `{ "anchor": "<name>", "role": "catalog" }` (e.g. modules).
4. For each source DB, **introspect** its Notion property names + types and write a
   `role_schemas["<anchor-or-id>"]` entry:
   - **core block** (required, engine-recognized): `title` `{col,type:title}`;
     `due_date` `{col,type:date}` (tasks) or `date`/`start`/`end` (schedule);
     `done_predicate` `{col,type:status,equals:"Done"}` **or** `{col,type:checkbox,equals:true}`;
     optional `week_predicate` `{col,equals:"This Week"}`.
   - **`fields`** (optional, typed, declared-only): every other column you want carried, each
     `{col,type}` where `type` ∈ title,date,select,status,checkbox,number,relation,rich_text,
     multi_select,people,url,email,phone_number. A date column may add `highlight:true` to
     become a **key date** (reminder) — see the key-date prompt below.
5. Enumerate `group` children under the anchor; each venture with a tasks-shaped DB goes into
   `resolved.groups.<area>` keyed by its Notion **page id**
   (`{label, role:"tasks", tasks_db:"<id>", cached_at}`); non-ventures into `resolved.ignored`.
   Provide `child_schema_defaults.tasks` (the core+fields schema new ventures inherit).
6. **Key-date prompt (off + ask, once):** when a source has more than one date column, the
   most due-like is `due_date`; register each *other* date column in `fields` as
   `{type:date, highlight:false}` and ask once — "New date column '<Col>' on <area> — make it
   a key date (surfaces as a reminder on its day)? (y/n)". `y` → set `highlight:true`. Store the
   decision; never re-ask.
7. Write `context/maps/<identity>.json`.

## Mode B — Incremental sync (map exists)
1. Re-verify each anchor resolves; re-discover or ask on a miss; update changed ids.
2. Re-enumerate `group` children; add new ventures / drop removed (tombstone), re-probe
   `resolved.ignored`.
3. Re-check each `role_schemas` entry against live properties: **new non-date column** → add
   to `fields` (typed, no prompt); **new date column** → add `{type:date,highlight:false}` and
   run the key-date prompt; **column removed** → warn + tombstone (don't silently break);
   **type changed** → update the field's `type` and warn that writes may shift.
4. Write `context/maps/<identity>.json`.

## Always — regenerate the human summary
Rewrite `context/notion.md` from the new-shape map: a readable tree of areas, sources,
ventures, and each source's core fields + declared `fields` (mark key dates). Banner:
`<!-- GENERATED from the Life-OS map by /refresh-notion — do not hand-edit -->`

## Report
Summarize changes: new/removed ventures, anchor moves, added/renamed/removed columns, type
changes, key-date decisions, or "nothing changed." Remind to `mapctl push` the map to the
store when done.
