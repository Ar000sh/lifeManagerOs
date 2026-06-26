# /refresh-notion — Build & sync the workspace map

Build or repair `context/lifeos.map.json`, then regenerate the human-readable
`context/notion.md`. This is the only skill that writes the **durable** map (`anchors`, `rules`, `db_role_schemas`, `task_roles`); consuming skills may lazily populate the disposable `resolved` cache per `context/resolver.md`. See
`context/resolver.md` for how the map is consumed.

## Mode A — Bootstrap (no map yet, or `--bootstrap`)
1. Find the workspace root: use `lifeos.map.json.workspace_root` if present; else
   `notion-search` for the user's Life-OS root page. If nothing is found, STOP and ask
   the user to (re)connect Notion.
2. From the root, discover the top-level sections and identify anchors:
   `business_root`, `university_section`, `university_tasks_db`, `modules_db`,
   `work_schedule_db`. When a candidate is ambiguous, ask ONE question (ask-then-remember).
3. For each operational DB, infer its **role** and **property-role schema** by inspecting
   its property names + types (title, date, select, relation, checkbox). Record the
   schema under `db_role_schemas`. Record select option labels you rely on under
   `status_values` (e.g. `done`, `this_week`).
4. Record enumeration `rules` (businesses are child pages under `business_root`, each with
   a tasks DB of role `business_tasks`). Enumerate the children: those WITH a
   `business_tasks`-shaped DB go into `resolved.businesses`; child pages that are NOT
   businesses (no such DB, e.g. notes/test pages) go into `resolved.ignored` so runtime
   skills don't re-probe them.
5. Set `task_roles` to the task-like roles to aggregate (default
   `["business_tasks","university_tasks"]`).
6. Write `context/lifeos.map.json`.

## Mode B — Incremental sync (map exists)
1. Re-verify each anchor still resolves; if one is gone, resolve-on-miss (re-discover) or
   ask. Update changed IDs.
2. Re-enumerate children under `business_root`; add new businesses / drop removed ones in
   `resolved.businesses`, and keep `resolved.ignored` current for non-business children.
3. Re-check each role's `db_role_schemas` against live properties; update renamed columns
   and new select options.
4. Write the updated `context/lifeos.map.json`.

## Always — regenerate the human summary
Rewrite `context/notion.md` from the map: a readable tree of sections, businesses, DBs,
and each DB's role + key properties. Add the banner:
`<!-- GENERATED from context/lifeos.map.json by /refresh-notion — do not hand-edit -->`

## Report
Summarize what changed: new/removed businesses, anchor moves, schema/option changes, or
"nothing changed." If a brand-new top-level section appeared that matches no rule, flag it
and ask whether to map it (ask-then-remember).
