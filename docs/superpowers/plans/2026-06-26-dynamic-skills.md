# Dynamic Life-OS Skills Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make `/today`, `/week`, `/add`, `/refresh-notion` work against any Notion workspace shape by resolving everything at runtime through a cached map, so they contain zero hardcoded IDs or column names.

**Architecture:** A data file `context/lifeos.map.json` holds stable *anchors* + *enumeration rules* + *property-role schemas* + a write-back *resolution cache*. A shared procedure `context/resolver.md` defines how every skill loads the map, resolves role instances (cache-first, enumerate-on-miss, write back), self-heals on miss, and asks-then-remembers on ambiguity. The four skills are rewritten to route every Notion access through that procedure. `/refresh-notion` becomes the mapper that builds/repairs the map and regenerates the human-readable `context/notion.md`.

**Tech Stack:** Markdown skill files (`.claude/commands/*.md`), a JSON data file, Notion MCP (`mcp__claude_ai_Notion__*`) and Google Calendar MCP (`mcp__claude_ai_Google_Calendar__*`) consumed at runtime by Claude. No application code is added.

## Global Constraints

- **No hardcoded Notion IDs or raw column names in any skill file.** All operational IDs live only in `context/lifeos.map.json`. Objective check: the no-ID grep in Task 8 must return zero matches over the four skills + `resolver.md`.
- **These are instruction (Markdown) + JSON artifacts, not executable code.** "Tests" mean: (1) JSON validity, (2) the automated no-ID grep, (3) manual live-workspace validation against Aroosh's real Notion. There is no pytest suite for skills — do not invent one.
- **Property access always goes through `db_role_schemas`** — never assume a column is named `Due Date`, `Status`, etc.
- **Source of truth vs cache:** `anchors` + `rules` + `db_role_schemas` are durable; `resolved` is a disposable, self-healing cache.
- **Timezone:** Europe/Berlin for all relative-date interpretation; store dates ISO-8601.
- **Notion reads:** prefer filtered queries via the official Notion API MCP (`notion-query-data-sources` / database queries with real property filters); use semantic search only as a fallback.
- **Commits:** Aroosh asked to hold commits this session. Each task ends with a *staged* change and a commit command, but **stage and ask for confirmation before actually committing** rather than auto-committing.
- **Scope line:** this project creates **records** (rows in existing DBs). Creating **structures** (new business pages, DBs, sections, views) is deferred to the Workspace-provisioning project (#3) and must NOT be added here.

---

## File Structure

- **Create** `context/lifeos.map.json` — the map (anchors, rules, db_role_schemas, task_roles, resolved cache). The ONLY file holding real Notion IDs.
- **Create** `context/resolver.md` — shared resolve procedure every skill references.
- **Modify** `.claude/commands/refresh-notion.md` — becomes the mapper/bootstrap; reads/writes the map; regenerates `notion.md`.
- **Modify** `.claude/commands/today.md` — resolve all task roles + schedule + calendar via resolver.
- **Modify** `.claude/commands/week.md` — same, over a 7-day window.
- **Modify** `.claude/commands/add.md` — route record creation to resolved destinations using the destination's property-role schema.
- **Modify** `context/notion.md` — becomes a "generated — do not hand-edit" human summary.
- **Modify (optional, OUTSIDE this repo)** `~/.claude/commands/life-os.md` — convert the global CRUD command to the resolver. Not committed with the repo.

---

## Map JSON shape (reference for all tasks)

Tasks below produce/consume exactly this shape. `task_roles` lists which roles `/today` and `/week` aggregate over (so adding a new task-like role later is a one-line change).

```json
{
  "workspace_root": "17f640b8-4c57-4cdb-8cb8-7de20d282e14",
  "anchors": {
    "business_root":       "02b35e4e-891d-4c3b-a8a1-8b5f3a968c34",
    "university_section":  "25a31bbe-c66a-42d7-abd1-063ddf316f0e",
    "university_tasks_db": "580c2d1d-8813-4800-92a1-9db78568a1ca",
    "modules_db":          "5e62acec-3f74-49f7-a8b2-c4b6937ca4b3",
    "work_schedule_db":    "55f90404-8783-412a-9f9d-e6d5011bcc7a"
  },
  "rules": {
    "businesses": {
      "under": "business_root",
      "each_child_is": "a business page",
      "tasks_db_role": "business_tasks"
    }
  },
  "task_roles": ["business_tasks", "university_tasks"],
  "db_role_schemas": {
    "business_tasks": {
      "title": "Name", "status": "Status", "priority": "Priority",
      "type": "Type", "due_date": "Due Date", "business": "Business",
      "notes": "Notes", "parent": "Parent",
      "status_values": { "this_week": "This Week", "done": "Done" }
    },
    "university_tasks": {
      "title": "Name", "status": "Status", "priority": "Priority",
      "type": "Type", "due_date": "Due Date", "exam_date": "Exam Date",
      "grade": "Grade", "module": "Module", "notes": "Notes",
      "readonly": ["Module (Name)", "Semester Label"],
      "status_values": { "done": "Done" }
    },
    "modules": {
      "title": "Name", "semester": "Semester", "status": "Status",
      "credits": "Credits", "professor": "Professor", "notes": "Notes"
    },
    "schedule": {
      "title": "Name", "day": "Day", "date": "Date",
      "start": "Start Time", "end": "End Time",
      "recurring": "Recurring", "notes": "Notes"
    }
  },
  "resolved": {
    "businesses": {
      "Laundromat Hannover":         { "page": "39b55afae5704875a1641799948d8e38", "tasks_db": "fdffad80-a34c-44a0-a9ed-afb05acd232e", "role": "business_tasks", "cached_at": "2026-06-26" },
      "Van Company Czech Republic":  { "page": "b5397190ebbf48fb98d8f6de7f410790", "tasks_db": "ae28ef1d-5dec-45d2-b3ab-8132214d5361", "role": "business_tasks", "cached_at": "2026-06-26" },
      "TBHShop — Trip Back Home":    { "page": "37b121c0-adad-8127-b07b-f2af5016049d", "tasks_db": "6905803e-faa1-444a-877e-296a5dbfcdbd", "role": "business_tasks", "cached_at": "2026-06-26" },
      "Evening Dresses Export":      { "page": "37b121c0-adad-8140-a1f9-dd2d62f81eaa", "tasks_db": "b0cf87a9-fa93-4dd2-8d9c-b883f925537a", "role": "business_tasks", "cached_at": "2026-06-26" }
    }
  }
}
```

---

### Task 1: Seed the map data file

**Files:**
- Create: `context/lifeos.map.json`

**Interfaces:**
- Produces: the map file at `context/lifeos.map.json` with top-level keys `workspace_root`, `anchors`, `rules`, `task_roles`, `db_role_schemas`, `resolved` — exactly the shape in "Map JSON shape" above. All later tasks consume these key names.

- [ ] **Step 1: Write the file**

Create `context/lifeos.map.json` with the exact JSON from the "Map JSON shape" section above (copy it verbatim — real IDs seeded from the current `context/notion.md`).

- [ ] **Step 2: Verify it is valid JSON and has the required keys**

Run:
```bash
python -c "import json; d=json.load(open('context/lifeos.map.json', encoding='utf-8')); print(sorted(d)); assert set(d) >= {'workspace_root','anchors','rules','task_roles','db_role_schemas','resolved'}; assert len(d['anchors'])==5; assert d['db_role_schemas']['business_tasks']['due_date']=='Due Date'; print('OK')"
```
Expected: prints the sorted top-level keys then `OK` with no AssertionError.

- [ ] **Step 3: Verify every business in resolved has page + tasks_db**

Run:
```bash
python -c "import json; b=json.load(open('context/lifeos.map.json', encoding='utf-8'))['resolved']['businesses']; assert all('page' in v and 'tasks_db' in v for v in b.values()); print(len(b),'businesses OK')"
```
Expected: `4 businesses OK`

- [ ] **Step 4: Stage and (after confirmation) commit**

```bash
git add context/lifeos.map.json
git commit -m "feat(lifeos): add runtime resolution map seeded with current workspace IDs"
```

---

### Task 2: Write the shared resolver procedure

**Files:**
- Create: `context/resolver.md`

**Interfaces:**
- Consumes: the map keys from Task 1 (`anchors`, `rules`, `task_roles`, `db_role_schemas`, `resolved`, `workspace_root`).
- Produces: a documented procedure the four skills reference by the phrase **"Resolve targets via `context/resolver.md`."** Defines named operations the skills cite: *resolve role instances*, *resolve a named business*, *property lookup*, *resolve-on-miss*, *ambiguity → ask-then-remember*, *write-back*.

- [ ] **Step 1: Write `context/resolver.md`**

```markdown
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
```

- [ ] **Step 2: Verify required sections exist**

Run:
```bash
rg -nc "Resolve-on-miss|ask-then-remember|Property lookup|Workspace safety|write-back|write each back" context/resolver.md
```
Expected: at least 5 matching lines (the procedure's key operations are present).

- [ ] **Step 3: Verify it references the map file and contains no operational IDs**

Run:
```bash
rg -n "context/lifeos.map.json" context/resolver.md && rg -nE "[0-9a-f]{32}|collection://" context/resolver.md; echo "exit:$?"
```
Expected: the first match prints; the ID grep prints nothing and `echo` shows a non-zero exit (no IDs found).

- [ ] **Step 4: Stage and (after confirmation) commit**

```bash
git add context/resolver.md
git commit -m "feat(lifeos): add shared resolver procedure for runtime Notion resolution"
```

---

### Task 3: Rewrite `/refresh-notion` as the mapper/bootstrap

**Files:**
- Modify: `.claude/commands/refresh-notion.md` (full rewrite)
- Modify: `context/notion.md` (add generated-file banner)

**Interfaces:**
- Consumes: map shape (Task 1), resolver concepts (Task 2).
- Produces: behavior that writes/repairs `context/lifeos.map.json` and regenerates `context/notion.md`. No other task depends on its prose, but it is the only writer of the map.

- [ ] **Step 1: Replace the file contents**

Replace all of `.claude/commands/refresh-notion.md` with:

```markdown
# /refresh-notion — Build & sync the workspace map

Build or repair `context/lifeos.map.json`, then regenerate the human-readable
`context/notion.md`. This is the ONLY skill that writes the map. See
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
   a tasks DB of role `business_tasks`). Enumerate current businesses into
   `resolved.businesses`.
5. Set `task_roles` to the task-like roles to aggregate (default
   `["business_tasks","university_tasks"]`).
6. Write `context/lifeos.map.json`.

## Mode B — Incremental sync (map exists)
1. Re-verify each anchor still resolves; if one is gone, resolve-on-miss (re-discover) or
   ask. Update changed IDs.
2. Re-enumerate businesses under `business_root`; add new ones / drop removed ones in
   `resolved.businesses`.
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
```

- [ ] **Step 2: Add the generated banner to `context/notion.md`**

Add as the very first line of `context/notion.md`:
```
<!-- GENERATED from context/lifeos.map.json by /refresh-notion — do not hand-edit -->
```

- [ ] **Step 3: Verify no hardcoded IDs remain in the skill**

Run:
```bash
rg -nE "[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}|[0-9a-f]{32}|collection://" .claude/commands/refresh-notion.md; echo "exit:$?"
```
Expected: no output, non-zero exit (no IDs).

- [ ] **Step 4: Verify both modes and the regenerate step are documented**

Run:
```bash
rg -nc "Mode A — Bootstrap|Mode B — Incremental|regenerate the human summary|db_role_schemas" .claude/commands/refresh-notion.md
```
Expected: at least 4 matches.

- [ ] **Step 5: Stage and (after confirmation) commit**

```bash
git add .claude/commands/refresh-notion.md context/notion.md
git commit -m "feat(lifeos): rewrite /refresh-notion as map builder/sync"
```

---

### Task 4: Rewrite `/today`

**Files:**
- Modify: `.claude/commands/today.md` (full rewrite)

**Interfaces:**
- Consumes: resolver (Task 2), `task_roles` + `schedule` schema + `db_role_schemas` (Task 1).
- Produces: `/today` behavior with no IDs. No task depends on it.

- [ ] **Step 1: Replace the file contents**

Replace all of `.claude/commands/today.md` with:

```markdown
# /today — Daily Briefing

Structured morning briefing for today. Pull live data — don't summarize from memory.
**Resolve all Notion targets via `context/resolver.md`.** Prefer filtered Notion API
queries over semantic search.

## Steps
1. Get today's date in Europe/Berlin.
2. **Calendar** — fetch today's events via the Google Calendar MCP list-events tool.
   Show time + title.
3. **Tasks (all task roles)** — resolve every source for the map's `task_roles`
   (each business's `business_tasks` DB + the `university_tasks` DB). For each, query
   items where the role's `due_date` (or `exam_date` for university) is today or earlier
   and `status` ≠ the role's `done` value. Use each role's `db_role_schemas` for the real
   property names.
4. **Work shift today** — resolve the `schedule` source (work_schedule_db) and find
   entries where the `date` property = today.
5. If a source fails to resolve, self-heal per the resolver; if it still fails, include
   the rest and flag the broken one rather than aborting.

## Output Format
---
**📅 [Day, Date]**

**🗓 Calendar**
- [time] Event name  (or "none")

**🎓 University**
- [URGENT if overdue] Task name — Due: date (Module)  (or "none")

**💼 Work**
- Shift: Start–End  (or "No shift today")

**🚀 Business**
- Task name [Priority] — Business name  (or "none")

**Quick note:** [one-sentence observation]
---
```

- [ ] **Step 2: Verify no hardcoded IDs and resolver is referenced**

Run:
```bash
rg -n "context/resolver.md" .claude/commands/today.md && rg -nE "[0-9a-f]{32}|collection://" .claude/commands/today.md; echo "exit:$?"
```
Expected: resolver reference prints; ID grep prints nothing, non-zero exit.

- [ ] **Step 3: Stage and (after confirmation) commit**

```bash
git add .claude/commands/today.md
git commit -m "feat(lifeos): make /today resolve task roles dynamically"
```

---

### Task 5: Rewrite `/week`

**Files:**
- Modify: `.claude/commands/week.md` (full rewrite)

**Interfaces:**
- Consumes: resolver (Task 2), `task_roles` + `schedule` schema (Task 1).
- Produces: `/week` behavior with no IDs.

- [ ] **Step 1: Replace the file contents**

Replace all of `.claude/commands/week.md` with:

```markdown
# /week — Weekly Overview

Structured view of the current week (Mon–Sun, Europe/Berlin). Pull live data.
**Resolve all Notion targets via `context/resolver.md`.** Prefer filtered Notion API
queries over semantic search.

## Steps
1. Determine the current week (Monday–Sunday) in Europe/Berlin.
2. **Calendar** — fetch all events for the week via the Google Calendar MCP list-events
   tool.
3. **Work shifts** — resolve the `schedule` source; fetch entries whose `date` falls in
   the week.
4. **University deadlines** — resolve the `university_tasks` source; fetch items whose
   `due_date` or `exam_date` is within the week and `status` ≠ `done`; sort ascending.
5. **Business tasks** — resolve every `business_tasks` source (all businesses); fetch
   items whose `status` = the role's `this_week` value or whose `due_date` is within the
   week.
6. Self-heal failed sources per the resolver; flag any that stay broken.

## Output Format
Group by day; skip empty days.
---
**📆 Week of [Mon Date] – [Sun Date]**

**Monday, [Date]**
- 🗓 [time] Calendar event
- 💼 Work: [Start–End] or —
- 🎓 [Task name] due (Module)
- 🚀 [Business task] [Priority]

… (each day) …

**Summary**
- X university deadlines, X business tasks, X work shifts
- [one actionable note]
---
```

- [ ] **Step 2: Verify no hardcoded IDs and resolver is referenced**

Run:
```bash
rg -n "context/resolver.md" .claude/commands/week.md && rg -nE "[0-9a-f]{32}|collection://" .claude/commands/week.md; echo "exit:$?"
```
Expected: resolver reference prints; ID grep prints nothing, non-zero exit.

- [ ] **Step 3: Stage and (after confirmation) commit**

```bash
git add .claude/commands/week.md
git commit -m "feat(lifeos): make /week resolve task roles dynamically"
```

---

### Task 6: Rewrite `/add`

**Files:**
- Modify: `.claude/commands/add.md` (full rewrite)

**Interfaces:**
- Consumes: resolver (Task 2), all `db_role_schemas` (Task 1), the `businesses` rule.
- Produces: `/add` behavior with no IDs; record creation only.

- [ ] **Step 1: Replace the file contents**

Replace all of `.claude/commands/add.md` with:

```markdown
# /add — Add a record

Add a task, university item, exam, work shift, module, or calendar event to the right
place. **Resolve all Notion targets via `context/resolver.md`.** This skill creates
**records** (rows) only — it does NOT create new businesses, databases, sections, or
views (that is the workspace-provisioning project).

## Routing
| What the user says | Role / destination |
|---|---|
| task / to-do for a business | `business_tasks` of that business (resolve by name under the `businesses` rule) |
| university task / assignment / study session | `university_tasks` |
| exam | `university_tasks`, Type = Exam, set `exam_date` |
| work shift | `schedule` |
| new module / course | `modules` |
| meeting / appointment / event with a time | Google Calendar |
| reminder | Google Calendar |

If the destination is unclear, ask ONE question: "Business, University, Work, or Calendar?"
If a business name is given but not yet in the map, resolve-on-miss (enumerate under
`business_root`); if it does not exist, say so — do NOT create a new business here.

## Creating in Notion
Use `notion-create-pages` into the resolved DB. Set columns via the destination role's
`db_role_schemas` (never assume column names). Defaults: set `title`; set `status` to a
sensible start value; set `priority` = Medium if not given; set `due_date` if mentioned.
For a university task tied to a module: resolve `modules`, search the module page, set the
`module` relation. For exams set both `due_date` (prep-by) and `exam_date` if known.

## Creating in Google Calendar
Use the Google Calendar MCP create-event tool. Always set start + end (default 1h).
Timezone: Europe/Berlin.

## Cross-posting
If adding an exam or important deadline in Notion, ask: "Also add a reminder in Google
Calendar?"

## Confirm
One line: "Added **[Name]** to [destination] — [key detail]."
```

- [ ] **Step 2: Verify no hardcoded IDs, resolver referenced, scope line present**

Run:
```bash
rg -n "context/resolver.md" .claude/commands/add.md && rg -nc "does NOT create new businesses" .claude/commands/add.md && rg -nE "[0-9a-f]{32}|collection://" .claude/commands/add.md; echo "exit:$?"
```
Expected: resolver reference + the scope line print; ID grep prints nothing, non-zero exit.

- [ ] **Step 3: Stage and (after confirmation) commit**

```bash
git add .claude/commands/add.md
git commit -m "feat(lifeos): make /add route record creation via resolver"
```

---

### Task 7 (optional, OUTSIDE this repo): Convert the global `life-os` command

> Lives at `~/.claude/commands/life-os.md`, not in this repo — it cannot be committed with the project. Do this only if Aroosh wants the global CRUD command made dynamic too. It is currently the worst hardcoded-ID offender and is stale (missing TBHShop + Evening Dresses).

**Files:**
- Modify: `C:\Users\Saturn\.claude\commands\life-os.md` (full rewrite)

**Interfaces:**
- Consumes: resolver (Task 2). Because it is global, it must reference the resolver/map by
  absolute project path or note that it only applies when run inside the Life-OS project.

- [ ] **Step 1: Replace contents** with a CRUD manager that resolves every target via the
  project's `context/resolver.md` + `context/lifeos.map.json` instead of the embedded tree.
  Keep the operations table (add/update/mark-done/list) but drop ALL IDs and the inline
  schemas; defer to `db_role_schemas`. Note it operates on whatever Life-OS project is
  active and requires the map to exist.

- [ ] **Step 2: Verify no hardcoded IDs remain**

Run:
```bash
rg -nE "[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}|[0-9a-f]{32}|collection://" "$HOME/.claude/commands/life-os.md"; echo "exit:$?"
```
Expected: no output, non-zero exit.

- [ ] **Step 3:** No commit (outside repo). Tell Aroosh it was updated in place.

---

### Task 8: Final verification

**Files:** none (verification only)

- [ ] **Step 1: Objective no-hardcoded-ID check across all four skills + resolver**

Run:
```bash
rg -nE "[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}|[0-9a-f]{32}|collection://" .claude/commands/today.md .claude/commands/week.md .claude/commands/add.md .claude/commands/refresh-notion.md context/resolver.md; echo "exit:$?"
```
Expected: **no output**, non-zero exit. This is the pass/fail gate for "the skills are dynamic."

- [ ] **Step 2: Map still valid**

Run:
```bash
python -c "import json; json.load(open('context/lifeos.map.json', encoding='utf-8')); print('map OK')"
```
Expected: `map OK`

- [ ] **Step 3: Manual live validation (run against Aroosh's real Notion — record results)**

Perform and confirm each (these need the live workspace; no automation):
- Parity: `/today` and `/week` return the same tasks/shifts/deadlines as before this change.
- Routing: `/add` places a task, an exam, a shift, a module, and a calendar event correctly.
- New-business: add a dummy business page + tasks DB in Notion → `/today` includes it with
  no skill/map edits (auto-enumeration writes it to `resolved`).
- Renamed-column: rename a task DB's `Due Date` → run `/refresh-notion` → `/today` still
  filters correctly via the updated `db_role_schemas`.
- Moved-anchor: move a section → resolve-on-miss re-discovers and updates the map.
- Ambiguity: two task-like DBs under one business → resolver asks once and remembers.
- Safety: disconnect / wrong workspace → skills stop and prompt to reconnect (no empty
  briefing).

- [ ] **Step 4: Clean up the dummy business** created during the new-business test.

---

## Self-Review

**Spec coverage:**
- Roles + anchors + property-role schemas + write-back cache → Task 1 (map) + Task 2 (resolver). ✅
- Resolver procedure incl. resolve-on-miss, ask-then-remember, workspace safety → Task 2. ✅
- `/refresh-notion` becomes mapper/bootstrap + regenerates `notion.md` → Task 3. ✅
- `/today`, `/week`, `/add` stripped of IDs, route via resolver → Tasks 4–6. ✅
- Records-vs-structures scope line (no structure creation) → Task 6 step 1 + Global Constraints. ✅
- Error handling (wrong workspace, anchor moved, ambiguity, stale cache, partial failure) → Task 2 steps 4–6, Task 4 step 1.5. ✅
- Validation suite (parity, new-business, renamed-column, moved-anchor, ambiguity, safety, no-ID grep) → Task 8. ✅
- Out of scope (#2 org skills, #3 provisioning, #4 multi-user store) → not planned here, per Global Constraints. ✅
- Extra discovered: global `life-os.md` hardcoded + stale → Task 7 (optional, outside repo). ✅

**Placeholder scan:** no TBD/TODO; every skill rewrite shows full file content; every verify step has a runnable command + expected output. ✅

**Type/name consistency:** key names (`workspace_root`, `anchors`, `rules`, `task_roles`,
`db_role_schemas`, `resolved`, `status_values`, role names `business_tasks` /
`university_tasks` / `modules` / `schedule`) are used identically in Tasks 1, 2, 4, 5, 6, 8. ✅
```
