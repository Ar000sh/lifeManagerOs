# Dynamic Task/Record Schema Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the hardcoded task field vocabulary with a map-driven, typed schema where each record type declares its own core (required, engine-recognized) and dynamic (optional, open-vocabulary) fields.

**Architecture:** Each Notion source's schema becomes a self-describing structure: a **core block** (`title`, `due_date`, `done_predicate`, optional `week_predicate`) that defines "what makes a record," plus a **`fields`** table of optional, typed, declared-only fields. Read decodes values from Notion's payload and keeps only declared fields; write builds Notion payloads from each field's declared `type`. "Exams" generalize to `highlight`-flagged date fields ("key dates"). A generic `Record` replaces `TaskRecord`.

**Tech Stack:** Python 3.10, dataclasses, httpx, pytest. Notion REST. FastMCP server (untouched except one docstring).

## Global Constraints

- Run tests from the `lifeos-mcp/` directory. Full suite: `../telegram-bot/.venv/Scripts/python.exe -m pytest -q`. Targeted: `../telegram-bot/.venv/Scripts/python.exe -m pytest tests/<file>.py -q`.
- Commit-per-task on branch `feat/dynamic-skills`, **local, no push**. End every commit message with the trailer:
  `Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>`
- TDD: write the failing test first, watch it fail, implement minimally, watch it pass, commit.
- **Green at every task boundary.** During the cutover (Tasks 4–7) not-yet-migrated consumers run against `LEGACY_FIXTURE_MAP`/`LEGACY_ALT_MAP`; each migration task repoints its own tests to the new `FIXTURE_MAP`/`ALT_MAP`. Task 8 deletes the legacy fixtures and old accessors. After every task, the **full suite passes**.
- `due_date` is strictly required to create a task (decided in the spec).
- Spec: `docs/superpowers/specs/2026-06-29-dynamic-task-schema-design.md`.

---

## File Structure

- `lifeos_mcp/notion_client.py` — `extract_props` (full type decode), `build_props` (type-driven via `TYPE_BUILDERS`).
- `lifeos_mcp/resolver_schema.py` — schema accessors: `schema_for`, `field_def`, `col`, `required_core`, `is_complete`, `week_match`, `key_date_fields` (old `prop`/`is_done` removed in Task 8).
- `lifeos_mcp/models.py` — add `KeyDate`, `Record`; change `AreaBlock.exams`→`key_dates`; remove `TaskRecord` (Task 8).
- `lifeos_mcp/tools/get_today.py`, `get_week.py`, `query_records.py`, `add_record.py` — consume the new accessors/model.
- `lifeos_mcp/server.py` — one docstring word.
- `tests/fixtures/maps.py` — new-shape `FIXTURE_MAP`/`ALT_MAP` (+ transient `LEGACY_*`).
- `tests/test_*.py` — updated per task.

---

### Task 1: Full-type `extract_props`

Additive — extends decoding to `number` and `relation`; existing behavior unchanged. Full suite stays green.

**Files:**
- Modify: `lifeos_mcp/notion_client.py:18-32`
- Test: `tests/test_notion_client.py`

**Interfaces:**
- Produces: `extract_props(page: dict) -> dict[str, Any]` — `{column_name: value}` decoded from the page payload's own per-property type. `date`→ISO `str` (the `start`), `number`→`float|int`, `relation`→`list[str]` of ids, `checkbox`→`bool`, `select`/`status`→`str|None`, `title`/`rich_text`→`str`.

- [ ] **Step 1: Write the failing test**

```python
def test_extract_props_reads_number_and_relation():
    page = {"properties": {
        "Estimate": {"type": "number", "number": 3.5},
        "Module": {"type": "relation", "relation": [{"id": "mod-1"}, {"id": "mod-2"}]}}}
    props = extract_props(page)
    assert props["Estimate"] == 3.5
    assert props["Module"] == ["mod-1", "mod-2"]
```

Add it to `tests/test_notion_client.py`.

- [ ] **Step 2: Run test to verify it fails**

Run: `../telegram-bot/.venv/Scripts/python.exe -m pytest tests/test_notion_client.py::test_extract_props_reads_number_and_relation -q`
Expected: FAIL — `KeyError: 'Estimate'` (number/relation not decoded).

- [ ] **Step 3: Add the two branches**

In `extract_props`, before the final `return out`, add inside the loop (after the `rich_text` branch):

```python
        elif t == "number":
            out[name] = v.get("number")
        elif t == "relation":
            out[name] = [r.get("id") for r in v.get("relation", [])]
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `../telegram-bot/.venv/Scripts/python.exe -m pytest tests/test_notion_client.py -q`
Expected: PASS (new test + existing `test_extract_props_reads_select_and_date`).

- [ ] **Step 5: Commit**

```bash
git add lifeos_mcp/notion_client.py tests/test_notion_client.py
git commit -m "feat(lifeos-mcp): extract_props decodes number and relation types

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 2: New schema accessors + new-shape fixtures (alongside legacy)

Adds the new accessors and the new-shape maps **without removing** `prop`/`is_done`. Existing consumers are repointed to `LEGACY_*` fixtures so they stay green.

**Files:**
- Modify: `lifeos_mcp/resolver_schema.py` (add accessors; keep `prop`/`is_done`)
- Modify: `tests/fixtures/maps.py` (new-shape `FIXTURE_MAP`/`ALT_MAP`; add `LEGACY_FIXTURE_MAP`/`LEGACY_ALT_MAP` = current content)
- Modify imports in: `tests/test_resolver_schema.py`, `tests/test_tools_today.py`, `tests/test_tools_week.py`, `tests/test_tools_query.py`, `tests/test_tools_add.py`, `tests/test_portability.py` → import the `LEGACY_*` names (aliased to the old local names).
- Test: `tests/test_resolver_schema.py` (add new-accessor tests)

**Interfaces:**
- Produces (in `resolver_schema.py`):
  - `CORE_KEYS: dict[str, tuple]` and `REQUIRED: dict[str, tuple]`
  - `field_def(schema: dict, key: str) -> dict | None`
  - `col(schema: dict, key: str) -> str | None`
  - `required_core(schema: dict) -> list[str]`
  - `is_complete(schema: dict, props: dict) -> bool`
  - `week_match(schema: dict, props: dict) -> bool`
  - `key_date_fields(schema: dict) -> list[tuple[str, dict]]`
- Produces (in `tests/fixtures/maps.py`): new-shape `FIXTURE_MAP`, `ALT_MAP`; legacy copies `LEGACY_FIXTURE_MAP`, `LEGACY_ALT_MAP`.

- [ ] **Step 1: Replace the fixtures file**

Overwrite `tests/fixtures/maps.py` with the new-shape maps **plus** the legacy copies. The new maps keep identical `anchors`/`areas`/`group`/`resolved`; only `role_schemas` and `child_schema_defaults` change shape.

```python
FIXTURE_MAP = {
    "workspace_root": "ws-root",
    "anchors": {
        "business_root": "biz-root",
        "university_tasks_db": "uni-tasks",
        "modules_db": "mod-db",
        "work_schedule_db": "work-db",
    },
    "areas": {
        "ventures": {"label": "Business", "emoji": "🚀",
                     "group": {"under": "business_root", "child_sources": [{"role": "tasks"}]}},
        "university": {"label": "University", "emoji": "🎓",
                       "sources": [{"anchor": "university_tasks_db", "role": "tasks"}],
                       "catalog": {"anchor": "modules_db", "role": "catalog"}},
        "work": {"label": "Work", "emoji": "💼",
                 "sources": [{"anchor": "work_schedule_db", "role": "schedule"}]},
    },
    "role_schemas": {
        "university_tasks_db": {
            "role": "tasks",
            "title": {"col": "Name", "type": "title"},
            "due_date": {"col": "Due Date", "type": "date"},
            "done_predicate": {"col": "Status", "type": "status", "equals": "Done"},
            "week_predicate": {"col": "Status", "equals": "This Week"},
            "fields": {
                "status": {"col": "Status", "type": "status"},
                "priority": {"col": "Priority", "type": "select"},
                "exam_date": {"col": "Exam Date", "type": "date", "highlight": True},
                "module": {"col": "Module", "type": "relation"},
            },
        },
        "work_schedule_db": {
            "role": "schedule",
            "title": {"col": "Name", "type": "title"},
            "date": {"col": "Date", "type": "date"},
            "start": {"col": "Start Time", "type": "rich_text"},
            "end": {"col": "End Time", "type": "rich_text"},
            "fields": {},
        },
        "modules_db": {
            "role": "catalog",
            "title": {"col": "Name", "type": "title"},
            "fields": {"semester": {"col": "Semester", "type": "rich_text"}},
        },
    },
    "child_schema_defaults": {
        "tasks": {
            "role": "tasks",
            "title": {"col": "Name", "type": "title"},
            "due_date": {"col": "Due Date", "type": "date"},
            "done_predicate": {"col": "Status", "type": "status", "equals": "Done"},
            "week_predicate": {"col": "Status", "equals": "This Week"},
            "fields": {
                "status": {"col": "Status", "type": "status"},
                "priority": {"col": "Priority", "type": "select"},
            },
        },
    },
    "resolved": {
        "groups": {"ventures": {
            "laundro-page": {"label": "Laundromat Hannover", "role": "tasks",
                             "tasks_db": "laundro-db", "cached_at": "2026-06-26"}}},
        "tombstones": {}, "ignored": [],
    },
}

ALT_MAP = {
    "workspace_root": "alt-root",
    "anchors": {"client_root": "client-root", "todo_db": "todo-db"},
    "areas": {
        "clients": {"label": "Clients", "emoji": "🧾",
                    "group": {"under": "client-root", "child_sources": [{"role": "tasks"}]}},
        "personal": {"label": "Persönlich", "emoji": "🏠",
                     "sources": [{"anchor": "todo_db", "role": "tasks"}]},
    },
    "role_schemas": {
        "todo_db": {
            "role": "tasks",
            "title": {"col": "Titel", "type": "title"},
            "due_date": {"col": "Fällig", "type": "date"},
            "done_predicate": {"col": "Erledigt", "type": "checkbox", "equals": True},
            "fields": {},
        },
    },
    "child_schema_defaults": {
        "tasks": {
            "role": "tasks",
            "title": {"col": "Name", "type": "title"},
            "due_date": {"col": "Due", "type": "date"},
            "done_predicate": {"col": "Status", "type": "status", "equals": "Done"},
            "fields": {"status": {"col": "Status", "type": "status"}},
        },
    },
    "resolved": {"groups": {"clients": {}}, "tombstones": {}, "ignored": []},
}

# ── transient legacy copies (old flat shape) — deleted in Task 8 ──
LEGACY_FIXTURE_MAP = {
    "workspace_root": "ws-root",
    "anchors": {"business_root": "biz-root", "university_tasks_db": "uni-tasks",
                "modules_db": "mod-db", "work_schedule_db": "work-db"},
    "areas": {
        "ventures": {"label": "Business", "emoji": "🚀",
                     "group": {"under": "business_root", "child_sources": [{"role": "tasks"}]}},
        "university": {"label": "University", "emoji": "🎓",
                       "sources": [{"anchor": "university_tasks_db", "role": "tasks"}],
                       "catalog": {"anchor": "modules_db", "role": "catalog"}},
        "work": {"label": "Work", "emoji": "💼",
                 "sources": [{"anchor": "work_schedule_db", "role": "schedule"}]},
    },
    "role_schemas": {
        "university_tasks_db": {"role": "tasks", "title": "Name", "status": "Status",
                                "priority": "Priority", "due_date": "Due Date",
                                "exam_date": "Exam Date", "catalog_rel": "Module",
                                "status_values": {"done": "Done", "this_week": "This Week"}},
        "work_schedule_db": {"role": "schedule", "title": "Name", "date": "Date",
                             "start": "Start Time", "end": "End Time"},
        "modules_db": {"role": "catalog", "title": "Name", "semester": "Semester"},
    },
    "child_schema_defaults": {
        "tasks": {"title": "Name", "status": "Status", "priority": "Priority",
                  "due_date": "Due Date",
                  "status_values": {"done": "Done", "this_week": "This Week"}},
    },
    "resolved": {
        "groups": {"ventures": {
            "laundro-page": {"label": "Laundromat Hannover", "role": "tasks",
                             "tasks_db": "laundro-db", "cached_at": "2026-06-26"}}},
        "tombstones": {}, "ignored": [],
    },
}

LEGACY_ALT_MAP = {
    "workspace_root": "alt-root",
    "anchors": {"client_root": "client-root", "todo_db": "todo-db"},
    "areas": {
        "clients": {"label": "Clients", "emoji": "🧾",
                    "group": {"under": "client-root", "child_sources": [{"role": "tasks"}]}},
        "personal": {"label": "Persönlich", "emoji": "🏠",
                     "sources": [{"anchor": "todo_db", "role": "tasks"}]},
    },
    "role_schemas": {
        "todo_db": {"role": "tasks", "title": "Titel", "due_date": "Fällig",
                    "done_when": {"property": "Erledigt", "equals": True}},
    },
    "child_schema_defaults": {
        "tasks": {"title": "Name", "due_date": "Due", "status": "Status",
                  "status_values": {"done": "Done"}},
    },
    "resolved": {"groups": {"clients": {}}, "tombstones": {}, "ignored": []},
}
```

- [ ] **Step 2: Repoint legacy consumers' imports**

In each of these files, change the fixture import to the legacy alias so the still-old code keeps passing:

- `tests/test_resolver_schema.py:2` → `from tests.fixtures.maps import LEGACY_FIXTURE_MAP as FIXTURE_MAP, LEGACY_ALT_MAP as ALT_MAP`
- `tests/test_tools_today.py:5` → `from tests.fixtures.maps import LEGACY_FIXTURE_MAP as FIXTURE_MAP`
- `tests/test_tools_week.py:5` → `from tests.fixtures.maps import LEGACY_FIXTURE_MAP as FIXTURE_MAP`
- `tests/test_tools_query.py:3` → `from tests.fixtures.maps import LEGACY_FIXTURE_MAP as FIXTURE_MAP`
- `tests/test_tools_add.py:4` → `from tests.fixtures.maps import LEGACY_FIXTURE_MAP as FIXTURE_MAP`
- `tests/test_portability.py:5` → `from tests.fixtures.maps import LEGACY_ALT_MAP as ALT_MAP` (and the inner import at line 26 → `from tests.fixtures.maps import LEGACY_ALT_MAP as ALT_MAP`)

Leave `tests/test_resolver_areas.py` and `tests/test_resolver_stale.py` importing `FIXTURE_MAP` (new) — they exercise discovery/reconcile, not field schema, and the new map preserves all anchors/areas/group/resolved.

- [ ] **Step 3: Write the failing accessor tests**

Replace the body of `tests/test_resolver_schema.py` below its (now legacy-aliased) imports — keep the existing four legacy tests, and **add** these new ones that use the new-shape maps directly:

```python
from tests.fixtures.maps import FIXTURE_MAP as NEW_FIXTURE_MAP, ALT_MAP as NEW_ALT_MAP
from lifeos_mcp.resolver_schema import (
    field_def, col, required_core, is_complete, week_match, key_date_fields)

def test_col_core_and_dynamic():
    sch = NEW_FIXTURE_MAP["role_schemas"]["university_tasks_db"]
    assert col(sch, "due_date") == "Due Date"          # core
    assert col(sch, "exam_date") == "Exam Date"        # dynamic
    assert col(sch, "nope") is None

def test_required_core_is_title_and_due_date():
    sch = NEW_FIXTURE_MAP["role_schemas"]["university_tasks_db"]
    assert required_core(sch) == ["title", "due_date"]

def test_is_complete_status_and_checkbox():
    uni = NEW_FIXTURE_MAP["role_schemas"]["university_tasks_db"]
    assert is_complete(uni, {"Status": "Done"}) is True
    assert is_complete(uni, {"Status": "Open"}) is False
    todo = NEW_ALT_MAP["role_schemas"]["todo_db"]
    assert is_complete(todo, {"Erledigt": True}) is True
    assert is_complete(todo, {"Erledigt": False}) is False

def test_week_match_uses_predicate():
    sch = NEW_FIXTURE_MAP["role_schemas"]["university_tasks_db"]
    assert week_match(sch, {"Status": "This Week"}) is True
    assert week_match(sch, {"Status": "Open"}) is False

def test_key_date_fields_only_highlighted_dates():
    sch = NEW_FIXTURE_MAP["role_schemas"]["university_tasks_db"]
    keys = [k for k, _ in key_date_fields(sch)]
    assert keys == ["exam_date"]
```

- [ ] **Step 4: Run to verify the new tests fail**

Run: `../telegram-bot/.venv/Scripts/python.exe -m pytest tests/test_resolver_schema.py -q`
Expected: FAIL — `ImportError: cannot import name 'field_def'`.

- [ ] **Step 5: Add the accessors**

Append to `lifeos_mcp/resolver_schema.py` (do NOT remove `prop`/`is_done` yet):

```python
CORE_KEYS = {"tasks": ("title", "due_date"),
             "schedule": ("title", "date", "start", "end"),
             "catalog": ("title",)}
REQUIRED = {"tasks": ("title", "due_date"),
            "schedule": ("title", "date"),
            "catalog": ("title",)}

def field_def(schema: dict, key: str) -> dict | None:
    top = schema.get(key)
    if isinstance(top, dict) and "col" in top:
        return top
    return schema.get("fields", {}).get(key)

def col(schema: dict, key: str) -> str | None:
    d = field_def(schema, key)
    return d.get("col") if d else None

def required_core(schema: dict) -> list[str]:
    return [k for k in REQUIRED.get(schema.get("role"), ("title",)) if col(schema, k)]

def is_complete(schema: dict, props: dict) -> bool:
    p = schema.get("done_predicate")
    return bool(p) and props.get(p["col"]) == p.get("equals", True)

def week_match(schema: dict, props: dict) -> bool:
    p = schema.get("week_predicate")
    return bool(p) and props.get(p["col"]) == p.get("equals")

def key_date_fields(schema: dict) -> list[tuple[str, dict]]:
    return [(k, d) for k, d in schema.get("fields", {}).items()
            if d.get("type") == "date" and d.get("highlight")]
```

- [ ] **Step 6: Run the full suite**

Run: `../telegram-bot/.venv/Scripts/python.exe -m pytest -q`
Expected: PASS (all 62 + new accessor tests; legacy consumers on `LEGACY_*`).

- [ ] **Step 7: Commit**

```bash
git add lifeos_mcp/resolver_schema.py tests/fixtures/maps.py tests/test_resolver_schema.py \
        tests/test_tools_today.py tests/test_tools_week.py tests/test_tools_query.py \
        tests/test_tools_add.py tests/test_portability.py
git commit -m "feat(lifeos-mcp): add typed schema accessors + new-shape fixtures (legacy retained)

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 3: `Record` + `KeyDate` models (additive)

Add the new dataclasses alongside `TaskRecord` (do not touch `AreaBlock` yet).

**Files:**
- Modify: `lifeos_mcp/models.py`
- Test: `tests/test_models.py`

**Interfaces:**
- Produces: `KeyDate(label: str, date: date)` with `.to_dict()`; `Record(id, role, title, due_date, overdue, area_label, source_id, key_dates=[], fields={}, source_label=None, url=None)` with `.to_dict()`. `Record.fields` values are JSON-safe (strings/numbers/bools/lists from `extract_props`).

- [ ] **Step 1: Write the failing test**

Add to `tests/test_models.py`:

```python
def test_record_to_dict_with_key_dates_and_fields():
    from lifeos_mcp.models import Record, KeyDate
    from datetime import date
    r = Record(id="1", role="tasks", title="Essay", due_date=date(2026, 6, 27),
               overdue=False, area_label="University", source_id="uni-tasks",
               key_dates=[KeyDate(label="Exam Date", date=date(2026, 7, 10))],
               fields={"priority": "High"}, source_label=None, url="http://n/1")
    d = r.to_dict()
    assert d["title"] == "Essay"
    assert d["due_date"] == "2026-06-27"
    assert d["key_dates"] == [{"label": "Exam Date", "date": "2026-07-10"}]
    assert d["fields"] == {"priority": "High"}
```

- [ ] **Step 2: Run to verify it fails**

Run: `../telegram-bot/.venv/Scripts/python.exe -m pytest tests/test_models.py::test_record_to_dict_with_key_dates_and_fields -q`
Expected: FAIL — `ImportError: cannot import name 'Record'`.

- [ ] **Step 3: Add the dataclasses**

In `lifeos_mcp/models.py`, after the `_iso` helper, add:

```python
@dataclass
class KeyDate:
    label: str; date: date
    def to_dict(self) -> dict:
        return {"label": self.label, "date": _iso(self.date)}

@dataclass
class Record:
    id: str; role: str; title: str
    due_date: date | None; overdue: bool
    area_label: str; source_id: str
    key_dates: list = field(default_factory=list)
    fields: dict = field(default_factory=dict)
    source_label: str | None = None
    url: str | None = None
    def to_dict(self) -> dict:
        return {"id": self.id, "role": self.role, "title": self.title,
                "due_date": _iso(self.due_date), "overdue": self.overdue,
                "area_label": self.area_label, "source_id": self.source_id,
                "key_dates": [k.to_dict() for k in self.key_dates],
                "fields": self.fields, "source_label": self.source_label,
                "url": self.url}
```

(`field` and `date` are already imported at the top of `models.py`.)

- [ ] **Step 4: Run the full suite**

Run: `../telegram-bot/.venv/Scripts/python.exe -m pytest -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add lifeos_mcp/models.py tests/test_models.py
git commit -m "feat(lifeos-mcp): add generic Record + KeyDate models

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 4: Migrate `get_today` → Record + key dates; `AreaBlock.exams`→`key_dates`

**Files:**
- Modify: `lifeos_mcp/tools/get_today.py`
- Modify: `lifeos_mcp/models.py` (`AreaBlock`)
- Modify: `tests/test_models.py` (AreaBlock test), `tests/test_tools_today.py`, `tests/test_portability.py` (repoint to new fixtures + add key-date/required-flag tests)

**Interfaces:**
- Consumes: `col`, `is_complete`, `key_date_fields` (Task 2); `Record`, `KeyDate`, `AreaBlock` (Task 3 + this task).
- Produces: `get_today(...)` returning `TodayPayload` whose `AreaBlock` has `tasks: list[Record]`, `key_dates: list[dict]` (`{title, label, date}`), `shift`. `_task_rows(...) -> tuple[list[Record], list[dict]]`.

- [ ] **Step 1: Change `AreaBlock` and update its model test**

In `lifeos_mcp/models.py` replace the `AreaBlock` dataclass:

```python
@dataclass
class AreaBlock:
    label: str; emoji: str; tasks: list
    key_dates: list; shift: ScheduleRecord | None
    def to_dict(self) -> dict:
        return {"label": self.label, "emoji": self.emoji,
                "tasks": [t.to_dict() for t in self.tasks],
                "key_dates": self.key_dates,
                "shift": self.shift.to_dict() if self.shift else None}
```

In `tests/test_models.py`, update `test_today_payload_to_dict_nested` to construct `AreaBlock(label="Work", emoji="💼", tasks=[], key_dates=[], shift=None)`.

- [ ] **Step 2: Write the failing get_today tests**

Repoint the import in `tests/test_tools_today.py:5` to `from tests.fixtures.maps import FIXTURE_MAP` (new). Repoint `tests/test_portability.py:5` and `:26` to `from tests.fixtures.maps import ALT_MAP` (new). Then add these tests to `tests/test_tools_today.py`:

```python
def _row_exam(title, status, due, exam):
    r = _row(title, status, due)
    r["properties"]["Exam Date"] = {"type": "date", "date": {"start": exam}}
    return r

def test_today_surfaces_key_dates_not_exams():
    m = copy.deepcopy(FIXTURE_MAP)
    m.setdefault("resolved", {}).setdefault("reconciled", {})["ventures"] = "2026-06-27"
    notion = FakeNotionClient(rows={
        "uni-tasks": [_row_exam("ML", "Open", "2026-06-27", "2026-07-10")]})
    p = get_today(m, notion, FakeCalendarClient(), date(2026, 6, 27))
    kds = [kd for a in p.areas for kd in a.key_dates]
    assert {"title": "ML", "label": "Exam Date", "date": "2026-07-10"} in kds

def test_today_flags_missing_required_due_date():
    m = copy.deepcopy(FIXTURE_MAP)
    m.setdefault("resolved", {}).setdefault("reconciled", {})["ventures"] = "2026-06-27"
    bad = {"id": "x", "url": "u", "properties": {
        "Name": {"type": "title", "title": [{"plain_text": "No date"}]},
        "Status": {"type": "select", "select": {"name": "Open"}}}}
    notion = FakeNotionClient(rows={"uni-tasks": [bad]})
    p = get_today(m, notion, FakeCalendarClient(), date(2026, 6, 27))
    assert any("missing required due_date" in w for w in p.warnings)
```

- [ ] **Step 3: Run to verify failure**

Run: `../telegram-bot/.venv/Scripts/python.exe -m pytest tests/test_tools_today.py -q`
Expected: FAIL — current `get_today` builds `TaskRecord`/`exams` and reads new-shape schema via old `prop` (returns dicts), so assertions and attribute access fail.

- [ ] **Step 4: Rewrite `get_today.py`**

Replace the imports and the `_task_rows`/`get_today` bodies (keep `_to_date`, `_day_window`, `_shift` signatures; `_shift` switches `prop`→`col`):

```python
from datetime import date, datetime, time
from zoneinfo import ZoneInfo
from ..models import Record, KeyDate, ScheduleRecord, EventRecord, AreaBlock, TodayPayload
from ..resolver_areas import resolve_sources, iter_areas
from ..resolver_schema import col, is_complete, key_date_fields
from ..notion_client import extract_props
from ..resolver_stale import reconcile_due_groups, reconcile_group
from ..errors import NotionNotFound, WorkspaceUnavailable

def _to_date(s):
    return date.fromisoformat(s[:10]) if s else None

def _day_window(d: date, tz: str) -> tuple[str, str]:
    zone = ZoneInfo(tz)
    return (datetime.combine(d, time.min, zone).isoformat(),
            datetime.combine(d, time.max, zone).isoformat())

def _task_rows(map, notion, source, today, warnings, stale_groups):
    tasks, key_dates = [], []
    try:
        rows = notion.query_data_source(source.source_id)
    except Exception as exc:
        warnings.append(f"task source {source.source_id} failed: {exc}")
        if isinstance(exc, NotionNotFound) and source.source_label:
            stale_groups.add(source.area_key)
        return tasks, key_dates
    sch = source.schema
    title_col, due_col = col(sch, "title"), col(sch, "due_date")
    kd_fields = key_date_fields(sch)
    for row in rows:
        props = extract_props(row)
        if is_complete(sch, props):
            continue
        rid = row.get("id", "")
        title = props.get(title_col) if title_col else None
        due = _to_date(props.get(due_col)) if due_col else None
        if not title:
            warnings.append(f"task {rid} missing required title")
        if due_col and not due:
            warnings.append(f"task {rid} missing required due_date")
        rec_fields = {}
        for k, d in sch.get("fields", {}).items():
            v = props.get(d["col"])
            if v is not None:
                rec_fields[k] = v
        rec_key_dates = []
        for k, d in kd_fields:
            kv = _to_date(props.get(d["col"]))
            if kv:
                rec_key_dates.append(KeyDate(label=d["col"], date=kv))
                key_dates.append({"title": title or "", "label": d["col"],
                                  "date": kv.isoformat()})
        rec = Record(id=rid, role="tasks", title=title or "", due_date=due,
                     overdue=bool(due and due < today), area_label=source.area_label,
                     source_id=source.source_id, key_dates=rec_key_dates,
                     fields=rec_fields, source_label=source.source_label,
                     url=row.get("url"))
        if due and due <= today:
            tasks.append(rec)
    return tasks, key_dates

def _shift(map, notion, source, today, warnings):
    try:
        rows = notion.query_data_source(source.source_id)
    except Exception as exc:
        warnings.append(f"schedule source {source.source_id} failed: {exc}")
        return None
    sch = source.schema
    for row in rows:
        props = extract_props(row)
        d = _to_date(props.get(col(sch, "date"))) if col(sch, "date") else None
        if d == today:
            return ScheduleRecord(id=row.get("id", ""),
                title=props.get(col(sch, "title")) or "", date=d,
                start=props.get(col(sch, "start")) if col(sch, "start") else None,
                end=props.get(col(sch, "end")) if col(sch, "end") else None,
                source_id=source.source_id)
    return None

def get_today(map, notion, calendar, today: date, tz: str = "Europe/Berlin") -> TodayPayload:
    warnings: list[str] = []
    reconcile_due_groups(map, notion, today, warnings)
    task_sources = resolve_sources(map, notion, "tasks", warnings)
    sched_sources = resolve_sources(map, notion, "schedule", warnings)
    stale_groups: set[str] = set()
    blocks = []
    for area in iter_areas(map):
        a_tasks, a_key_dates, a_shift = [], [], None
        for s in (s for s in task_sources if s.area_key == area["key"]):
            ts, kds = _task_rows(map, notion, s, today, warnings, stale_groups)
            a_tasks += ts; a_key_dates += kds
        for s in (s for s in sched_sources if s.area_key == area["key"]):
            a_shift = a_shift or _shift(map, notion, s, today, warnings)
        if a_tasks or a_key_dates or a_shift:
            blocks.append(AreaBlock(area["label"], area["emoji"], a_tasks, a_key_dates, a_shift))
    for area_key in stale_groups:
        try:
            reconcile_group(map, notion, area_key)
        except WorkspaceUnavailable:
            raise
        except Exception as exc:
            warnings.append(f"reconcile {area_key} failed: {exc}")
    events = []
    try:
        tmin, tmax = _day_window(today, tz)
        events = [EventRecord(**e) for e in calendar.list_events(tmin, tmax)]
    except Exception as exc:
        warnings.append(f"calendar failed: {exc}")
    return TodayPayload(date=today, areas=blocks, events=events, warnings=warnings)
```

- [ ] **Step 5: Run the full suite**

Run: `../telegram-bot/.venv/Scripts/python.exe -m pytest -q`
Expected: PASS. (`test_tools_today` + `test_portability` now on new fixtures; `get_week`/`query_records`/`add_record` still on `LEGACY_*`.)

- [ ] **Step 6: Commit**

```bash
git add lifeos_mcp/tools/get_today.py lifeos_mcp/models.py tests/test_models.py \
        tests/test_tools_today.py tests/test_portability.py
git commit -m "feat(lifeos-mcp): get_today emits Record + key_dates, flags missing required

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 5: Migrate `get_week` → key dates + week_predicate

**Files:**
- Modify: `lifeos_mcp/tools/get_week.py`
- Modify: `tests/test_tools_week.py` (repoint to new `FIXTURE_MAP` + add a key-date test)

**Interfaces:**
- Consumes: `col`, `is_complete`, `week_match`, `key_date_fields`.
- Produces: `get_week(...)` returning `WeekPayload`; each day dict has `tasks`, `key_dates` (`{title, area, source_label, status, due_date, label, date}`), `shift`, `events`; `summary` has `tasks`, `key_dates`, `shifts`.

- [ ] **Step 1: Repoint import + write the failing test**

Change `tests/test_tools_week.py:5` to `from tests.fixtures.maps import FIXTURE_MAP` (new). Add:

```python
def test_week_buckets_key_dates_in_range():
    m = copy.deepcopy(FIXTURE_MAP)
    m.setdefault("resolved", {}).setdefault("reconciled", {})["ventures"] = "2026-06-27"
    row = {"id": "t1", "url": "u", "properties": {
        "Name": {"type": "title", "title": [{"plain_text": "ML"}]},
        "Status": {"type": "select", "select": {"name": "Open"}},
        "Due Date": {"type": "date", "date": {"start": "2026-06-25"}},
        "Exam Date": {"type": "date", "date": {"start": "2026-06-24"}}}}
    notion = FakeNotionClient(rows={"uni-tasks": [row]})
    payload = get_week(m, notion, FakeCalendarClient(), date(2026, 6, 27))
    kds = [k for d in payload.days for k in d["key_dates"]]
    assert any(k["title"] == "ML" and k["label"] == "Exam Date" for k in kds)
    assert payload.summary["key_dates"] >= 1
```

- [ ] **Step 2: Run to verify failure**

Run: `../telegram-bot/.venv/Scripts/python.exe -m pytest tests/test_tools_week.py -q`
Expected: FAIL — old `get_week` uses `prop` on new-shape schema and has no `key_dates` bucket.

- [ ] **Step 3: Rewrite `get_week.py`**

Replace imports and body:

```python
from datetime import date, timedelta
from ..models import EventRecord, WeekPayload
from ..resolver_areas import resolve_sources
from ..resolver_schema import col, is_complete, week_match, key_date_fields
from ..notion_client import extract_props
from ..resolver_stale import reconcile_due_groups, reconcile_group
from ..errors import NotionNotFound, WorkspaceUnavailable
from .get_today import _to_date, _day_window

def week_bounds(today: date) -> tuple[date, date]:
    start = today - timedelta(days=today.weekday())
    return start, start + timedelta(days=6)

def get_week(map, notion, calendar, today: date, tz: str = "Europe/Berlin") -> WeekPayload:
    start, end = week_bounds(today)
    warnings: list[str] = []
    reconcile_due_groups(map, notion, today, warnings)
    buckets: dict[str, dict] = {}
    def bucket(d): return buckets.setdefault(d.isoformat(),
        {"date": d.isoformat(), "tasks": [], "key_dates": [], "shift": None, "events": []})

    stale_groups: set[str] = set()
    for s in resolve_sources(map, notion, "tasks", warnings):
        try:
            rows = notion.query_data_source(s.source_id)
        except Exception as exc:
            warnings.append(f"task source {s.source_id} failed: {exc}")
            if isinstance(exc, NotionNotFound) and s.source_label:
                stale_groups.add(s.area_key)
            continue
        sch = s.schema
        title_col, due_col, status_col = col(sch, "title"), col(sch, "due_date"), col(sch, "status")
        kd_fields = key_date_fields(sch)
        for row in rows:
            props = extract_props(row)
            if is_complete(sch, props):
                continue
            due = _to_date(props.get(due_col)) if due_col else None
            title = props.get(title_col) or ""
            status = props.get(status_col) if status_col else None
            item = {"title": title, "area": s.area_label, "source_label": s.source_label,
                    "status": status, "due_date": due.isoformat() if due else None}
            for k, d in kd_fields:
                kv = _to_date(props.get(d["col"]))
                if kv and start <= kv <= end:
                    bucket(kv)["key_dates"].append({**item, "label": d["col"],
                                                    "date": kv.isoformat()})
            if due and start <= due <= end:
                bucket(due)["tasks"].append(item)
            elif week_match(sch, props):
                bucket(start)["tasks"].append(item)

    for s in resolve_sources(map, notion, "schedule", warnings):
        try:
            rows = notion.query_data_source(s.source_id)
        except Exception as exc:
            warnings.append(f"schedule {s.source_id} failed: {exc}"); continue
        sch = s.schema
        for row in rows:
            props = extract_props(row)
            d = _to_date(props.get(col(sch, "date"))) if col(sch, "date") else None
            if d and start <= d <= end:
                bucket(d)["shift"] = {"title": props.get(col(sch, "title")) or "",
                    "start": props.get(col(sch, "start")) if col(sch, "start") else None,
                    "end": props.get(col(sch, "end")) if col(sch, "end") else None}

    for area_key in stale_groups:
        try:
            reconcile_group(map, notion, area_key)
        except WorkspaceUnavailable:
            raise
        except Exception as exc:
            warnings.append(f"reconcile {area_key} failed: {exc}")

    try:
        evs = calendar.list_events(_day_window(start, tz)[0], _day_window(end, tz)[1])
        for e in evs:
            d = _to_date(e["start"])
            if d: bucket(d)["events"].append(EventRecord(**e).to_dict())
    except Exception as exc:
        warnings.append(f"calendar failed: {exc}")

    days = [buckets[k] for k in sorted(buckets)]
    summary = {"tasks": sum(len(d["tasks"]) for d in days),
               "key_dates": sum(len(d["key_dates"]) for d in days),
               "shifts": sum(1 for d in days if d["shift"])}
    return WeekPayload(start=start, end=end, days=days, summary=summary, warnings=warnings)
```

(Note: this also adds the same `NotionNotFound`→`stale_groups` self-heal the old version had; behavior preserved.)

- [ ] **Step 4: Run the full suite**

Run: `../telegram-bot/.venv/Scripts/python.exe -m pytest -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add lifeos_mcp/tools/get_week.py tests/test_tools_week.py
git commit -m "feat(lifeos-mcp): get_week buckets key_dates via highlight + week_predicate

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 6: Migrate `query_records`

**Files:**
- Modify: `lifeos_mcp/tools/query_records.py`
- Modify: `tests/test_tools_query.py` (repoint to new `FIXTURE_MAP`)

**Interfaces:**
- Consumes: `col`, `is_complete`.
- Produces: `query_records(map, notion, role, filters) -> list[dict]` — unchanged output keys (`id, title, status, due_date, area, source_label, source_id, url`); `status` resolved via the declared `status` field, `not_done` via `is_complete`.

- [ ] **Step 1: Repoint import**

Change `tests/test_tools_query.py:3` to `from tests.fixtures.maps import FIXTURE_MAP` (new). The existing three tests are the spec for this task (they assert status filtering + source_label).

- [ ] **Step 2: Run to verify failure**

Run: `../telegram-bot/.venv/Scripts/python.exe -m pytest tests/test_tools_query.py -q`
Expected: FAIL — old `query_records` calls `prop(sch, "status")` which returns a dict for new-shape schema, so the status filter mismatches.

- [ ] **Step 3: Rewrite `query_records.py`**

```python
from datetime import date
from ..resolver_areas import resolve_sources
from ..resolver_schema import col, is_complete
from ..notion_client import extract_props
from .get_today import _to_date

def query_records(map, notion, role: str, filters: dict | None = None) -> list[dict]:
    filters = filters or {}
    out = []
    for s in resolve_sources(map, notion, role):
        if filters.get("area"):
            hay = [s.area_label] + ([s.source_label] if s.source_label else [])
            if not any(filters["area"].lower() in h.lower() for h in hay):
                continue
        sch = s.schema
        title_col, status_col, due_col = col(sch, "title"), col(sch, "status"), col(sch, "due_date")
        try:
            rows = notion.query_data_source(s.source_id)
        except Exception:
            continue
        for row in rows:
            props = extract_props(row)
            status = props.get(status_col) if status_col else None
            due = _to_date(props.get(due_col)) if due_col else None
            if filters.get("not_done") and is_complete(sch, props): continue
            if filters.get("status") and status != filters["status"]: continue
            if filters.get("due_before") and not (due and due < date.fromisoformat(filters["due_before"])): continue
            if filters.get("due_after") and not (due and due > date.fromisoformat(filters["due_after"])): continue
            out.append({"id": row.get("id", ""), "title": props.get(title_col) or "",
                        "status": status, "due_date": due.isoformat() if due else None,
                        "area": s.area_label, "source_label": s.source_label,
                        "source_id": s.source_id, "url": row.get("url")})
    return out
```

- [ ] **Step 4: Run the full suite**

Run: `../telegram-bot/.venv/Scripts/python.exe -m pytest -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add lifeos_mcp/tools/query_records.py tests/test_tools_query.py
git commit -m "feat(lifeos-mcp): query_records uses typed schema accessors

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 7: Type-driven `build_props` (incl. relations) + `add_record` required check

**Files:**
- Modify: `lifeos_mcp/notion_client.py` (`build_props` + `TYPE_BUILDERS`)
- Modify: `lifeos_mcp/tools/add_record.py`
- Modify: `tests/test_notion_client.py` (build_props test → new shape + relation), `tests/test_tools_add.py` (repoint + add due_date to creating tests + add missing-required test)

**Interfaces:**
- Consumes: `field_def`, `col`, `required_core`.
- Produces: `build_props(schema: dict, fields: dict) -> dict` (type-driven); `add_record(map, notion, role, fields, area=None) -> dict` returning `{"created": False, "error": "missing_required", "fields": [...]}` when a required core field is absent.

- [ ] **Step 1: Rewrite the `build_props` test (new shape + relation)**

Replace `test_build_props_skips_none_and_maps_types` in `tests/test_notion_client.py` with:

```python
def test_build_props_typed_and_skips_none_and_relation():
    from lifeos_mcp.notion_client import build_props
    schema = {"role": "tasks",
              "title": {"col": "Name", "type": "title"},
              "due_date": {"col": "Due Date", "type": "date"},
              "fields": {"status": {"col": "Status", "type": "status"},
                         "module": {"col": "Module", "type": "relation"},
                         "notes": {"col": "Notes", "type": "rich_text"}}}
    out = build_props(schema, {"title": "Buy soap", "status": "Open",
                               "due_date": "2026-07-01", "module": ["mod-1"],
                               "notes": None, "missing_role": "x"})
    assert out["Name"]["title"][0]["text"]["content"] == "Buy soap"
    assert out["Status"]["status"]["name"] == "Open"
    assert out["Due Date"]["date"]["start"] == "2026-07-01"
    assert out["Module"]["relation"] == [{"id": "mod-1"}]
    assert "Notes" not in out                       # None skipped
    assert "missing_role" not in out and len(out) == 4
```

- [ ] **Step 2: Run to verify failure**

Run: `../telegram-bot/.venv/Scripts/python.exe -m pytest tests/test_notion_client.py::test_build_props_typed_and_skips_none_and_relation -q`
Expected: FAIL — old `build_props` reads `schema.get(role)` as a string column and has no relation support.

- [ ] **Step 3: Rewrite `build_props`**

In `lifeos_mcp/notion_client.py`, add the import at the top (`resolver_schema` does not import `notion_client`, so no cycle):

```python
from .resolver_schema import field_def
```

Replace `build_props` (lines 34-49) with:

```python
TYPE_BUILDERS = {
    "title":     lambda v: {"title": [{"text": {"content": str(v)}}]},
    "date":      lambda v: {"date": {"start": str(v)}},
    "select":    lambda v: {"select": {"name": str(v)}},
    "status":    lambda v: {"status": {"name": str(v)}},
    "checkbox":  lambda v: {"checkbox": bool(v)},
    "number":    lambda v: {"number": v},
    "relation":  lambda v: {"relation": [{"id": i} for i in v]},
    "rich_text": lambda v: {"rich_text": [{"text": {"content": str(v)}}]},
}

def build_props(schema: dict, fields: dict) -> dict:
    """Build Notion property payloads from each field's declared type."""
    props = {}
    for key, value in fields.items():
        d = field_def(schema, key)
        if not d or value is None:
            continue
        builder = TYPE_BUILDERS.get(d.get("type"))
        if builder:
            props[d["col"]] = builder(value)
    return props
```

- [ ] **Step 4: Repoint + fix the add tests, write the missing-required test**

In `tests/test_tools_add.py`: change line 4 to `from tests.fixtures.maps import FIXTURE_MAP` (new). Then add `"due_date"` to the three tests that expect creation with only a title:

- `test_add_task_to_area_by_label_resolves_anchor` (line 60): `{"title": "Read ch.3", "due_date": "2026-07-01"}`
- `test_add_to_named_business_reports_venture_destination` (line 66): `{"title": "Order soap", "due_date": "2026-07-01"}`
- `test_add_to_anchored_area_reports_area_destination` (line 72): `{"title": "Read ch.3", "due_date": "2026-07-01"}`

(The ambiguous/not-found tests at lines 21, 35, 44 are unchanged — they return before the required check.) Add:

```python
def test_add_refuses_missing_required_due_date():
    m = copy.deepcopy(FIXTURE_MAP)
    notion = FakeNotionClient()
    res = add_record(m, notion, "tasks", {"title": "No date"}, area="University")
    assert res["created"] is False
    assert res["error"] == "missing_required"
    assert res["fields"] == ["due_date"]
    assert notion.created == []
```

- [ ] **Step 5: Run to verify the add tests fail**

Run: `../telegram-bot/.venv/Scripts/python.exe -m pytest tests/test_tools_add.py -q`
Expected: FAIL — old `add_record` uses `prop` and has no required check.

- [ ] **Step 6: Rewrite `add_record.py`**

```python
from ..resolver_areas import resolve_sources
from ..resolver_schema import col, required_core
from ..notion_client import build_props

def _label(s):
    return s.source_label or s.area_label

def add_record(map, notion, role: str, fields: dict, area: str | None = None) -> dict:
    sources = resolve_sources(map, notion, role)
    if not sources:
        return {"created": False, "error": f"no source for role {role}"}

    if area:
        a = area.lower()
        candidates = [s for s in sources
                      if (s.source_label and a in s.source_label.lower())
                      or a in s.area_label.lower()]
        if not candidates:
            return {"created": False, "error": "destination_not_found",
                    "candidates": sorted({_label(s) for s in sources})}
    else:
        candidates = sources

    if len(candidates) > 1:
        return {"created": False, "error": "ambiguous_destination",
                "candidates": sorted({_label(s) for s in candidates})}

    target = candidates[0]
    sch = target.schema
    fields = dict(fields)
    missing = [k for k in required_core(sch) if k not in fields]
    if missing:
        return {"created": False, "error": "missing_required", "fields": missing}
    if col(sch, "priority") and "priority" not in fields:
        fields["priority"] = "Medium"
    props = build_props(sch, fields)
    page = notion.create_page(target.source_id, props)
    return {"created": True, "id": page.get("id"), "url": page.get("url"),
            "destination": _label(target)}
```

- [ ] **Step 7: Run the full suite**

Run: `../telegram-bot/.venv/Scripts/python.exe -m pytest -q`
Expected: PASS. No module imports `prop`/`is_done` anymore.

- [ ] **Step 8: Commit**

```bash
git add lifeos_mcp/notion_client.py lifeos_mcp/tools/add_record.py \
        tests/test_notion_client.py tests/test_tools_add.py
git commit -m "feat(lifeos-mcp): type-driven build_props (incl relations) + add_record required check

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 8: Cleanup — remove legacy fixtures, old accessors, TaskRecord

**Files:**
- Modify: `tests/fixtures/maps.py` (delete `LEGACY_FIXTURE_MAP`/`LEGACY_ALT_MAP`)
- Modify: `lifeos_mcp/resolver_schema.py` (delete `prop`, `is_done`)
- Modify: `lifeos_mcp/models.py` (delete `TaskRecord`)
- Modify: `tests/test_resolver_schema.py` (remove legacy tests + the `LEGACY_* as` aliases; keep new-accessor tests, importing `FIXTURE_MAP`/`ALT_MAP` directly)
- Modify: `tests/test_models.py` (delete `test_task_to_dict_serializes_date`)
- Modify: `lifeos_mcp/server.py:31` (docstring)

**Interfaces:**
- Produces: clean end state — no legacy fixtures, no `prop`/`is_done`, no `TaskRecord`.

- [ ] **Step 1: Verify nothing references the symbols to be removed**

Run: `../telegram-bot/.venv/Scripts/python.exe -m pytest -q` first to confirm green baseline, then grep:

```bash
grep -rn "LEGACY_FIXTURE_MAP\|LEGACY_ALT_MAP\|TaskRecord\|\bprop\b\|is_done" lifeos_mcp tests
```

Expected references only in: `tests/test_resolver_schema.py` (legacy tests + aliases), `tests/test_models.py` (`test_task_to_dict_serializes_date`), and the definitions themselves. If any *production* module under `lifeos_mcp/` still imports `prop`/`is_done`/`TaskRecord`, stop and migrate it (should not happen after Tasks 4–7).

- [ ] **Step 2: Delete legacy tests + aliases**

In `tests/test_resolver_schema.py`: remove the legacy-aliased import line and the four legacy tests (`test_prop_present_and_absent`, `test_is_done_via_status_value`, `test_is_done_via_checkbox_predicate`, `test_child_schema_default_used_when_source_absent`). Change the new-accessor import from `FIXTURE_MAP as NEW_FIXTURE_MAP, ALT_MAP as NEW_ALT_MAP` to plain `FIXTURE_MAP, ALT_MAP` and update the references in the new tests accordingly. In `tests/test_models.py`: delete `test_task_to_dict_serializes_date` and drop `TaskRecord` from its import.

- [ ] **Step 3: Delete the legacy fixtures**

In `tests/fixtures/maps.py`: delete `LEGACY_FIXTURE_MAP` and `LEGACY_ALT_MAP`.

- [ ] **Step 4: Delete old accessors + TaskRecord + fix docstring**

In `lifeos_mcp/resolver_schema.py`: delete `prop` and the old `is_done`. In `lifeos_mcp/models.py`: delete the `TaskRecord` dataclass. In `lifeos_mcp/server.py:31`: change the docstring to `"""Today's tasks, key dates, work shift, and calendar events across all areas."""`.

- [ ] **Step 5: Run the full suite**

Run: `../telegram-bot/.venv/Scripts/python.exe -m pytest -q`
Expected: PASS — full suite green with no legacy code.

- [ ] **Step 6: Final grep to confirm clean**

```bash
grep -rn "LEGACY_\|TaskRecord\|exam_date\|status_values\|done_when" lifeos_mcp
```
Expected: no matches in `lifeos_mcp/` (production code carries none of the old vocabulary).

- [ ] **Step 7: Commit**

```bash
git add lifeos_mcp/resolver_schema.py lifeos_mcp/models.py lifeos_mcp/server.py \
        tests/fixtures/maps.py tests/test_resolver_schema.py tests/test_models.py
git commit -m "refactor(lifeos-mcp): drop legacy schema vocabulary, TaskRecord, and fixtures

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Out of scope (per spec)

- `refresh-notion` introspection/discovery/prompt + drift handling (the `/refresh-notion` skill) — verified at Phase-B live validation, not unit-tested here.
- The template layer (authoring record types, required custom fields).
- Multi-user map/template storage.
- `query_records` warnings channel; `add_record`/`query_records` own-reconcile.

## Self-review notes

- **Spec coverage:** Section 1 schema → Task 2 (accessors) + Task 2 fixtures. Section 2 record/read → Tasks 3, 4 (+ extract_props Task 1). Section 3 write → Task 7. Section 4 refresh-notion → out of scope (skill, Phase B). Section 5 migration/testing → cutover structure across Tasks 2–8.
- **Required on read** (Section 2 step 4) → Task 4 `test_today_flags_missing_required_due_date`.
- **done_predicate both forms** → Task 2 `test_is_complete_status_and_checkbox` (status via FIXTURE, checkbox via ALT).
- **Relations gap closed** → Task 1 (read) + Task 7 (write).
- **Type consistency:** accessor names (`field_def`, `col`, `required_core`, `is_complete`, `week_match`, `key_date_fields`) are used identically in Tasks 4–7; `Record`/`KeyDate`/`AreaBlock.key_dates` consistent across models and consumers.
