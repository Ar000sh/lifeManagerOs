# Dynamic Task/Record Schema — Design

**Date:** 2026-06-29
**Branch:** `feat/dynamic-skills`
**Scope:** The schema/field model only. The future *template* layer (authoring/instantiating
record types, insisting on custom fields) is a separate spec that plugs into this. Multi-user
storage/onboarding is out of scope.

## Problem

The current record model is only *semi*-dynamic. Schema config makes Notion **column names**
configurable, but two things are still hardcoded in code:

1. **The set of fields.** `title, status, priority, due_date, exam_date` is a fixed vocabulary
   baked into `TaskRecord` (`models.py:9-20`), `get_today._task_rows`, and `get_week`.
   `exam_date` is a university-specific concept that leaked into the generic task pipeline.
2. **Field *types*.** `build_props` (`notion_client.py:34-48`) infers the Notion type from the
   field *name* (`due_date`/`exam_date`→date, `status`/`priority`→select, else→rich_text), and
   `extract_props` only handles a fixed subset of Notion types.

There is also no notion of **required** fields ("what makes a task"), and any Notion column not
in the hardcoded vocabulary is silently dropped. The goal of the restructuring is to make the
model dynamic enough to "switch things around and work for everyone," while still being able to
insist on the mandatory fields that make a record and stay flexible for per-user needs.

## Decisions (from brainstorming)

- **Scope:** schema/field model now; templates are a future consumer.
- **Mandatory enforcement:** *write-time + read-time.* Create refuses if a required field is
  missing; read still emits a non-conforming row but flags it in `warnings`.
- **Type source:** declared explicitly in the map (the map is authoritative). `refresh-notion`
  may *seed* types by introspecting Notion, but the map is the source of truth.
- **Flexibility model:** *open vocabulary, declared-only.* Any field can be declared (name +
  type); undeclared Notion columns are ignored, so output shape is predictable.
- **Exams generalize to "key dates":** a `highlight: true` flag on a date field surfaces it in a
  dedicated key-dates section. `exam_date` becomes an ordinary highlighted field — nothing special.
- **Key-date lifecycle:** always start with one canonical date (`due_date`); `refresh-notion`
  auto-discovers other date columns; a newly discovered date defaults to `highlight: false` and
  the agent **asks once** whether to make it a key date; the decision is stored in the map.
- **Required vs reserved split:** the **core** block (outside `fields`) is the required,
  engine-recognized contract; **`fields`** is dynamic and always optional. A required *custom*
  field is the future template layer's job, not this schema (decision A).
- **`due_date` is required on create** — a task needs a date (strict).

## Section 1 — Unified per-field schema

Replace the flat per-source bag with a **core block** (the contract that makes a record) plus a
**`fields`** table (dynamic, optional, declared-only). Each field is self-describing: `col`,
`type`, and flags.

```jsonc
"university_tasks_db": {
  "role": "tasks",

  // ── core: required + engine-recognized ("what makes a task") ──
  "title":          {"col": "Name",     "type": "title"},
  "due_date":       {"col": "Due Date", "type": "date"},
  "done_predicate": {"col": "Status",   "type": "status",  "equals": "Done"},
  "week_predicate": {"col": "Status",   "equals": "This Week"},   // optional

  // ── fields: dynamic, optional, declared-only, carried through ──
  "fields": {
    "priority":  {"col": "Priority",  "type": "select"},
    "exam_date": {"col": "Exam Date", "type": "date", "highlight": true},
    "module":    {"col": "Module",    "type": "relation"}
  }
}
```

Rules:

- **Core = the required set.** Presence in the core block means required; no separate `required`
  flag. For `role: tasks` the core is `title` + `due_date` (+ the predicates).
- **`done_predicate` references a column directly** (`col`/`type`/`equals`), so it is
  self-contained and does not depend on a display field being declared. Unifies today's two
  done-rules: status-value (`{col:"Status", type:"status", equals:"Done"}`) and checkbox
  (`{col:"Erledigt", type:"checkbox", equals:true}`).
- **`week_predicate`** (optional) replaces `status_values.this_week`: a row matching it is bucketed
  into the current week even without a due date in range.
- **`fields`** is open vocabulary — any name, any type — always optional, carried through.
- **Reserved field keys per role:** `tasks` → `title`, `due_date` (+ predicates);
  `schedule` → `title`, `date`, `start`, `end`. Everything else is plain: typed, carried,
  rendered by label, never special-cased by the engine.

Supported `type` values: `title`, `date`, `select`, `status`, `checkbox`, `number`, `relation`,
`rich_text`.

## Section 2 — Record model + read path

```python
@dataclass
class KeyDate:
    label: str          # the field's column/label, e.g. "Exam Date"
    date: date

@dataclass
class Record:
    id: str
    role: str
    title: str                      # core
    due_date: date | None           # core (engine-recognized)
    overdue: bool                   # engine-derived (due_date < today)
    key_dates: list[KeyDate]        # derived: fields with type=date + highlight
    fields: dict[str, Any]          # all OTHER declared dynamic fields present on the row
    area_label: str
    source_label: str | None
    source_id: str
    url: str | None
```

`TaskRecord` (`models.py:9-20`) is retired; `Record` replaces it for every Notion-row role.
`ScheduleRecord`/`EventRecord` stay (different reserved roles).

Read flow (`get_today._task_rows`, `get_week`):

1. `extract_props` is extended to decode the **full Notion type set from the page payload**
   (Notion self-describes each property's type): date→`date`, number→`float`, relation→list of
   ids, checkbox→`bool`, select/status→`str`, title/rich_text→`str`. It returns `{col: value}`
   for every property and does **not** need the schema.
2. The read step uses the **schema** to map columns→roles and keep declared-only: it pulls the
   core (`title`, `due_date`) and walks `fields` by `col`. The map's declared `type` is
   authoritative for writes and validation; on read it is used to identify which declared fields
   are dates (for `highlight`/key-date detection), while the *value* is decoded from Notion's
   payload.
3. Engine applies the core: filter via `done_predicate`; compute
   `overdue = bool(due_date and due_date < today)`.
4. **Required check:** a row missing `title` or `due_date` is **still emitted** and adds
   `warnings: ["task <id> missing required due_date"]`.
5. Walk `fields`: each present declared field → `record.fields[key]`; if declared `type=date` +
   `highlight` → also append a `KeyDate` to `record.key_dates`.
6. Undeclared Notion columns are ignored.

Output change: the per-area `exams` list becomes **`key_dates`**, aggregated across records in the
area and labeled by field. `AreaBlock.exams` → `AreaBlock.key_dates` (`models.py:42-49`); the
`/today` and `/week` formatters render a generic "⚠ Key dates" section instead of a hardcoded
"Exams" section.

## Section 3 — Write path

`build_props` (`notion_client.py:34-48`) stops inferring type from the field name. It walks the
source schema (core + `fields`) and uses the declared `type` to build the Notion payload via a
data-driven table:

```python
TYPE_BUILDERS = {
  "title":     lambda c, v: {c: {"title": [{"text": {"content": str(v)}}]}},
  "date":      lambda c, v: {c: {"date": {"start": str(v)}}},
  "select":    lambda c, v: {c: {"select": {"name": str(v)}}},
  "status":    lambda c, v: {c: {"status": {"name": str(v)}}},
  "checkbox":  lambda c, v: {c: {"checkbox": bool(v)}},
  "number":    lambda c, v: {c: {"number": v}},
  "relation":  lambda c, v: {c: {"relation": [{"id": i} for i in v]}},   # NEW
  "rich_text": lambda c, v: {c: {"rich_text": [{"text": {"content": str(v)}}]}},
}
```

This closes the **relations gap** the handoff flagged (a uni task can finally link its Module).

`add_record` (`add_record.py`) gains a required check before building anything:

```python
missing = [k for k in target.required_core if k not in fields]   # title, due_date
if missing:
    return {"created": False, "error": "missing_required", "fields": missing}
```

Destination resolution (the no-guess ambiguous/not-found logic, `add_record.py:13-26`) and the
priority default are unchanged. An unknown field key passed in is ignored (declared-only),
optionally echoed as a warning. `due_date` is in the required core, so creating a task without a
date is refused.

## Section 4 — refresh-notion: discovery, prompt, drift

Populates the schema so types are not hand-written, and owns the key-date lifecycle. The MCP
server stays non-interactive (it only reads the map); all discovery/prompting lives in the
`/refresh-notion` skill.

**Introspection.** When mapping a source, retrieve the Notion DB's property definitions (name +
Notion type) and write the typed schema into the map:

- The `title`-type property → core `title`.
- A date property → core `due_date`. If exactly one date column, it is unambiguously the due date
  (the "start with one" baseline). If multiple, the most due-like name is `due_date`; the rest
  become `fields` date entries.
- A status/checkbox property → wired into `done_predicate` by best match.
- Everything else → `fields` entries, typed, `highlight: false`.

**The prompt (off + ask).** When refresh finds a **new** date column not already in the map:

1. Register it in `fields` as `{type: date, highlight: false}`.
2. Ask: *"New date column 'Exam Date' on University tasks — make it a key date? (y/n)"*
3. `y` → `highlight: true`; `n` → leave it. Either way the decision is **stored** and never
   re-asked.

**Drift** (reuses the stale-reconcile machinery, `resolver_stale.py`):

- New non-date column → added to `fields`, typed, no prompt.
- A schema-referenced column disappears from Notion → flag (warning + tombstone), don't silently
  break reads.
- A column's type changes in Notion → update the map's type, warn that writes may shift.

## Section 5 — Migration + testing

**Migration — clean cutover, no back-compat shim.** The branch is unmerged and Phase B (live
Notion) has not started, so there is no production data to preserve.

- Rewrite `FIXTURE_MAP` / `ALT_MAP` (`tests/fixtures/maps.py`) into the new core/`fields` shape,
  including ALT_MAP's checkbox `done_when` → `done_predicate {type: checkbox, equals: true}`
  (also exercises the unified predicate).
- The real `lifeos.map.json` is regenerated by the upgraded `refresh-notion` (new shape +
  introspected types) — no hand-editing.

**Testing — TDD (this reshapes existing behavior):**

- *Schema-driven read:* `extract_props` returns correctly typed values per declared type;
  undeclared columns absent.
- *Required on read:* row missing `title`/`due_date` is still emitted **and** warns.
- *Required on write:* `add_record` without `due_date` → `{created:false,
  error:"missing_required", fields:["due_date"]}`.
- *Typed write:* each `type` builds the right Notion payload; **relation** round-trips.
- *done_predicate:* both status-value and checkbox forms filter correctly.
- *Key dates:* a `highlight` date field lands in `record.key_dates` and the area key-dates
  section; a non-highlight date stays inline in `record.fields`.
- *get_today/get_week:* `exams` → `key_dates` shape; existing 62 tests updated to the new model.
- *refresh-notion discovery/drift:* lives in the skill (conversational) → verified at Phase-B
  live-validation rather than unit-tested here (noted limitation).

## Out of scope / deferred

- The template layer (authoring record types, insisting on custom/required dynamic fields).
- Multi-user map/template storage and onboarding.
- `query_records`/`add_record` running their own reconcile (parked, separate spec).
- Live Notion validation of introspection (Phase B).
