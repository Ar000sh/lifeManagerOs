# lifeos MCP Server v1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a standalone Python MCP server (`lifeos-mcp/`) whose tools resolve the Notion workspace at runtime from `context/lifeos.map.json` and return clean structured data for `get_today`, `get_week`, `query_records`, `add_record`, `create_event` — then wire it into the Telegram bot and interactive Claude Code, retiring the markdown resolver.

**Architecture:** A FastMCP **stdio** server. Workspace-specific facts live only in the map (anchors + `areas` + `role_schemas` + a self-healing `resolved` cache). Pure resolver functions turn function-roles (`tasks`/`schedule`/`catalog`) into live IDs/columns; narrow Notion-REST and Google-Calendar client wrappers do all network I/O; five tools compose resolver + clients into structured JSON. The agent formats the response. Registered as a third stdio MCP server in `telegram-bot/agent_runner.py` and project `.mcp.json`, so one toolbox serves the bot, Claude Code, and desktop.

**Tech Stack:** Python 3.10+ (the bot's `telegram-bot/.venv` is 3.10.2 and launches the server via `sys.executable` in production — code must stay 3.10-compatible), `mcp` (FastMCP — already in `telegram-bot/.venv`), `httpx` (Notion REST), `google-api-python-client` + `google-auth` (Calendar), `pytest`. Notion API version header `2022-06-28`. The Claude Agent SDK (`claude_agent_sdk`) consumes the server at runtime.

**Execution environment (all Phase A tasks):** run tests with the bot venv interpreter `telegram-bot/.venv/Scripts/python.exe` (has pytest, httpx, mcp; google libs are NOT installed — fine, `calendar_client` imports them lazily). Invoke as `telegram-bot/.venv/Scripts/python.exe -m pytest ...` with the working directory set to `lifeos-mcp/`. `python` alone may not resolve to this venv on the Windows/git-bash shell.

## Global Constraints

- **No Notion IDs or raw column names anywhere in `lifeos-mcp/` except read from the map.** Objective gate: the grep in Task 16 returns zero matches in `*.py`.
- **Three function-roles only:** `tasks`, `schedule`, `catalog`. No `modules`/`business` role names in code — those are map labels.
- **Property access always via `role_schemas`**; a missing prop-role means the feature is absent for that source (return `None`, skip silently — rule D).
- **"Done" detection via `status_values.done` (select) OR `done_when` (checkbox)** — rule C; never assume a status-select.
- **Resolved group children keyed by stable Notion ID**, with `label` as a mutable attribute (rule i).
- **Never mutate the `resolved` cache on a transient or auth error**; if more than one entry fails to resolve in a run, treat as connection/permission and stop (blast-radius guard, rules ii–iii).
- **Timezone Europe/Berlin** for all relative-date logic; store/emit dates ISO-8601. Dates come from an **injectable clock**, never parsed from LLM free text.
- **Tools return JSON-serializable structured data; no presentation/formatting in tools.**
- **Records only:** `add_record` never creates areas, databases, sections, or businesses (project #3).
- **TDD:** write the failing test first; unit tests use fake clients + fixture maps and never touch the network.
- **Commits:** stage at each task's end and commit (the hold-commits constraint from the dynamic-skills session no longer applies; commit normally on this branch).

---

## File Structure

```
lifeos-mcp/
  pyproject.toml             # package metadata + deps (Task 1)
  lifeos_mcp/
    __init__.py
    config.py                # load/save map, read env tokens (Task 2)
    models.py                # dataclasses for structured payloads (Task 3)
    errors.py                # NotionNotFound / NotionAuthError / TransientError (Task 4)
    resolver_schema.py       # prop lookup + is_done (rules C, D) (Task 5)
    resolver_areas.py        # iter_areas / resolve_sources + group enum + write-back (Task 6)
    resolver_stale.py        # error classify, blast-radius guard, tombstones, re-enum (Task 7)
    notion_client.py         # NotionClient protocol + httpx impl (Task 8)
    calendar_client.py       # CalendarClient protocol + Google impl (Task 9)
    tools/
      __init__.py
      get_today.py           # (Task 10)
      get_week.py            # (Task 11)
      query_records.py       # (Task 12)
      add_record.py          # (Task 13)
      create_event.py        # (Task 13)
    server.py                # FastMCP app wiring (Task 14)
  tests/
    fixtures/maps.py         # FIXTURE_MAP + ALT_MAP (Task 3/5)
    fakes.py                 # FakeNotionClient / FakeCalendarClient (Task 5)
    test_config.py
    test_resolver_schema.py
    test_resolver_areas.py
    test_resolver_stale.py
    test_tools_today.py
    test_tools_week.py
    test_tools_query.py
    test_tools_add.py
    test_portability.py      # map-swap (Task 15)
```

Phase B touches existing files: `telegram-bot/agent_runner.py`, `.mcp.json`, `context/lifeos.map.json`, `context/resolver.md`, `.claude/commands/{today,week,add,refresh-notion}.md`.

---

## Map JSON shape (reference for all tasks)

```jsonc
{
  "workspace_root": "<id>",
  "anchors": { "business_root": "<id>", "university_tasks_db": "<id>",
               "modules_db": "<id>", "work_schedule_db": "<id>" },
  "areas": {
    "ventures":   { "label": "Business", "emoji": "🚀",
                    "group": { "under": "business_root", "child_sources": [ { "role": "tasks" } ] } },
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
                             "status_values": { "done": "Done", "this_week": "This Week" } },
    "work_schedule_db":    { "role": "schedule", "title": "Name", "date": "Date",
                             "start": "Start Time", "end": "End Time" },
    "modules_db":          { "role": "catalog", "title": "Name", "semester": "Semester" }
  },
  "child_schema_defaults": {
    "tasks": { "title": "Name", "status": "Status", "priority": "Priority",
               "due_date": "Due Date", "status_values": { "done": "Done", "this_week": "This Week" } }
  },
  "resolved": {
    "groups": { "ventures": { "<page_id>": { "label": "Laundromat Hannover", "role": "tasks",
                                             "tasks_db": "<id>", "cached_at": "2026-06-27" } } },
    "tombstones": {}, "ignored": []
  }
}
```

`child_schema_defaults[role]` supplies the property-role schema for enumerated group children (which share a common shape); a child may override via `resolved.groups.<area>.<id>.schema`.

---

### Task 1: Package scaffold

**Files:**
- Create: `lifeos-mcp/pyproject.toml`
- Create: `lifeos-mcp/lifeos_mcp/__init__.py`
- Create: `lifeos-mcp/tests/__init__.py`

**Interfaces:**
- Produces: an installable package `lifeos_mcp`; `pytest` runs from `lifeos-mcp/`.

- [ ] **Step 1: Write `pyproject.toml`**

```toml
[project]
name = "lifeos-mcp"
version = "0.1.0"
requires-python = ">=3.10"
dependencies = [
  "mcp>=1.0.0",
  "httpx>=0.27",
  "google-api-python-client>=2.0",
  "google-auth>=2.0",
  "google-auth-oauthlib>=1.0",
]

[project.optional-dependencies]
dev = ["pytest>=8.0"]

[tool.pytest.ini_options]
testpaths = ["tests"]
pythonpath = ["."]
```

- [ ] **Step 2: Create empty `lifeos_mcp/__init__.py` and `tests/__init__.py`**

Both files contain a single comment line: `# lifeos-mcp package` / `# tests`.

- [ ] **Step 3: Verify the package imports**

Run (from `lifeos-mcp/`): `python -c "import lifeos_mcp; print('ok')"`
Expected: `ok`

- [ ] **Step 4: Commit**

```bash
git add lifeos-mcp/pyproject.toml lifeos-mcp/lifeos_mcp/__init__.py lifeos-mcp/tests/__init__.py
git commit -m "feat(lifeos-mcp): scaffold server package"
```

---

### Task 2: Config — load/save map + env

**Files:**
- Create: `lifeos-mcp/lifeos_mcp/config.py`
- Test: `lifeos-mcp/tests/test_config.py`

**Interfaces:**
- Produces:
  - `load_map(path: str | Path) -> dict` — parse the map JSON (UTF-8).
  - `save_map(data: dict, path: str | Path) -> None` — write the map JSON (UTF-8, `indent=2`, `ensure_ascii=False`).
  - `@dataclass Settings(map_path: Path, notion_token: str, google_credentials: str, google_token_path: str, tz: str = "Europe/Berlin")`.
  - `load_settings(env: Mapping[str, str] | None = None) -> Settings` — reads `LIFEOS_MAP_PATH`, `NOTION_TOKEN`, `GOOGLE_OAUTH_CREDENTIALS`, `GOOGLE_CALENDAR_MCP_TOKEN_PATH`; defaults `LIFEOS_MAP_PATH` to `../context/lifeos.map.json` relative to the package.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_config.py
import json
from pathlib import Path
from lifeos_mcp.config import load_map, save_map, load_settings

def test_load_and_save_roundtrip(tmp_path: Path):
    p = tmp_path / "m.json"
    data = {"workspace_root": "x", "areas": {}, "resolved": {"groups": {}}}
    save_map(data, p)
    assert load_map(p) == data
    assert "\n" in p.read_text(encoding="utf-8")  # pretty-printed

def test_load_settings_reads_env(tmp_path: Path):
    s = load_settings({
        "LIFEOS_MAP_PATH": str(tmp_path / "m.json"),
        "NOTION_TOKEN": "tok",
        "GOOGLE_OAUTH_CREDENTIALS": "creds.json",
        "GOOGLE_CALENDAR_MCP_TOKEN_PATH": "token.json",
    })
    assert s.notion_token == "tok"
    assert s.tz == "Europe/Berlin"
```

- [ ] **Step 2: Run to verify it fails**

Run: `pytest tests/test_config.py -v`
Expected: FAIL with `ModuleNotFoundError: lifeos_mcp.config`.

- [ ] **Step 3: Implement `config.py`**

```python
import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping

_DEFAULT_MAP = Path(__file__).resolve().parent.parent.parent / "context" / "lifeos.map.json"

def load_map(path: str | Path) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))

def save_map(data: dict, path: str | Path) -> None:
    Path(path).write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")

@dataclass
class Settings:
    map_path: Path
    notion_token: str
    google_credentials: str
    google_token_path: str
    tz: str = "Europe/Berlin"

def load_settings(env: Mapping[str, str] | None = None) -> Settings:
    env = env if env is not None else os.environ
    return Settings(
        map_path=Path(env.get("LIFEOS_MAP_PATH", str(_DEFAULT_MAP))),
        notion_token=env.get("NOTION_TOKEN", "").strip(),
        google_credentials=env.get("GOOGLE_OAUTH_CREDENTIALS", "").strip(),
        google_token_path=env.get("GOOGLE_CALENDAR_MCP_TOKEN_PATH", "").strip(),
    )
```

- [ ] **Step 4: Run to verify it passes**

Run: `pytest tests/test_config.py -v`
Expected: PASS (2 passed).

- [ ] **Step 5: Commit**

```bash
git add lifeos-mcp/lifeos_mcp/config.py lifeos-mcp/tests/test_config.py
git commit -m "feat(lifeos-mcp): map load/save + settings"
```

---

### Task 3: Models + test fixtures

**Files:**
- Create: `lifeos-mcp/lifeos_mcp/models.py`
- Create: `lifeos-mcp/tests/fixtures/__init__.py`
- Create: `lifeos-mcp/tests/fixtures/maps.py`

**Interfaces:**
- Produces dataclasses, each with `to_dict() -> dict` (JSON-serializable; dates as ISO strings):
  - `TaskRecord(id, title, status, priority, due_date, exam_date, area_label, source_id, overdue, url, catalog=None)`
  - `ScheduleRecord(id, title, date, start, end, source_id)`
  - `EventRecord(id, title, start, end)`
  - `CatalogRecord(id, title, extra)`
  - `AreaBlock(label, emoji, tasks: list[TaskRecord], exams: list[TaskRecord], shift: ScheduleRecord | None)`
  - `TodayPayload(date, areas: list[AreaBlock], events: list[EventRecord], warnings: list[str])`
  - `WeekPayload(start, end, days: list[dict], summary: dict, warnings: list[str])`
- Produces `tests/fixtures/maps.py`: `FIXTURE_MAP` (the Map JSON shape above with synthetic IDs) and `ALT_MAP` (a differently shaped map: area label "Clients", a `done_when` checkbox task source, German column names).

- [ ] **Step 1: Write the failing test**

```python
# tests/test_models.py
from datetime import date
from lifeos_mcp.models import TaskRecord, TodayPayload, AreaBlock

def test_task_to_dict_serializes_date():
    t = TaskRecord(id="1", title="Pay rent", status="Open", priority="High",
                   due_date=date(2026, 6, 27), exam_date=None, area_label="Business",
                   source_id="db1", overdue=True, url="http://n/1")
    d = t.to_dict()
    assert d["due_date"] == "2026-06-27"
    assert d["overdue"] is True

def test_today_payload_to_dict_nested():
    p = TodayPayload(date=date(2026, 6, 27),
                     areas=[AreaBlock(label="Work", emoji="💼", tasks=[], exams=[], shift=None)],
                     events=[], warnings=[])
    d = p.to_dict()
    assert d["date"] == "2026-06-27"
    assert d["areas"][0]["label"] == "Work"
```

- [ ] **Step 2: Run to verify it fails**

Run: `pytest tests/test_models.py -v`
Expected: FAIL (`ModuleNotFoundError: lifeos_mcp.models`).

- [ ] **Step 3: Implement `models.py`**

```python
from dataclasses import dataclass, field
from datetime import date
from typing import Any

def _iso(d: date | None) -> str | None:
    return d.isoformat() if d else None

@dataclass
class TaskRecord:
    id: str; title: str; status: str | None; priority: str | None
    due_date: date | None; exam_date: date | None; area_label: str
    source_id: str; overdue: bool; url: str | None; catalog: str | None = None
    def to_dict(self) -> dict:
        return {"id": self.id, "title": self.title, "status": self.status,
                "priority": self.priority, "due_date": _iso(self.due_date),
                "exam_date": _iso(self.exam_date), "area_label": self.area_label,
                "source_id": self.source_id, "overdue": self.overdue,
                "url": self.url, "catalog": self.catalog}

@dataclass
class ScheduleRecord:
    id: str; title: str; date: date | None; start: str | None; end: str | None; source_id: str
    def to_dict(self) -> dict:
        return {"id": self.id, "title": self.title, "date": _iso(self.date),
                "start": self.start, "end": self.end, "source_id": self.source_id}

@dataclass
class EventRecord:
    id: str; title: str; start: str; end: str
    def to_dict(self) -> dict:
        return {"id": self.id, "title": self.title, "start": self.start, "end": self.end}

@dataclass
class CatalogRecord:
    id: str; title: str; extra: dict = field(default_factory=dict)
    def to_dict(self) -> dict:
        return {"id": self.id, "title": self.title, **self.extra}

@dataclass
class AreaBlock:
    label: str; emoji: str; tasks: list[TaskRecord]
    exams: list[TaskRecord]; shift: ScheduleRecord | None
    def to_dict(self) -> dict:
        return {"label": self.label, "emoji": self.emoji,
                "tasks": [t.to_dict() for t in self.tasks],
                "exams": [e.to_dict() for e in self.exams],
                "shift": self.shift.to_dict() if self.shift else None}

@dataclass
class TodayPayload:
    date: date; areas: list[AreaBlock]; events: list[EventRecord]; warnings: list[str]
    def to_dict(self) -> dict:
        return {"date": _iso(self.date), "areas": [a.to_dict() for a in self.areas],
                "events": [e.to_dict() for e in self.events], "warnings": self.warnings}

@dataclass
class WeekPayload:
    start: date; end: date; days: list[dict]; summary: dict; warnings: list[str]
    def to_dict(self) -> dict:
        return {"start": _iso(self.start), "end": _iso(self.end),
                "days": self.days, "summary": self.summary, "warnings": self.warnings}
```

- [ ] **Step 4: Write the fixtures**

Create `tests/fixtures/__init__.py` (empty). Create `tests/fixtures/maps.py` with `FIXTURE_MAP` = the "Map JSON shape" above with synthetic IDs (`"biz-root"`, `"uni-tasks"`, `"mod-db"`, `"work-db"`, one resolved venture `"laundro-page" -> tasks_db "laundro-db"`). Add `ALT_MAP`:

```python
# tests/fixtures/maps.py  (ALT_MAP excerpt — proves portability)
ALT_MAP = {
  "workspace_root": "alt-root",
  "anchors": {"client_root": "client-root", "todo_db": "todo-db"},
  "areas": {
    "clients": {"label": "Clients", "emoji": "🧾",
                "group": {"under": "client-root", "child_sources": [{"role": "tasks"}]}},
    "personal": {"label": "Persönlich", "emoji": "🏠",
                 "sources": [{"anchor": "todo_db", "role": "tasks"}]}
  },
  "role_schemas": {
    "todo_db": {"role": "tasks", "title": "Titel", "due_date": "Fällig",
                "done_when": {"property": "Erledigt", "equals": True}}
  },
  "child_schema_defaults": {
    "tasks": {"title": "Name", "due_date": "Due", "status": "Status",
              "status_values": {"done": "Done"}}
  },
  "resolved": {"groups": {"clients": {}}, "tombstones": {}, "ignored": []}
}
```

- [ ] **Step 5: Run to verify it passes**

Run: `pytest tests/test_models.py -v`
Expected: PASS (2 passed).

- [ ] **Step 6: Commit**

```bash
git add lifeos-mcp/lifeos_mcp/models.py lifeos-mcp/tests/fixtures lifeos-mcp/tests/test_models.py
git commit -m "feat(lifeos-mcp): payload models + map fixtures"
```

---

### Task 4: Error types + fakes

**Files:**
- Create: `lifeos-mcp/lifeos_mcp/errors.py`
- Create: `lifeos-mcp/tests/fakes.py`

**Interfaces:**
- Produces error classes: `NotionNotFound`, `NotionAuthError`, `TransientError`, `WorkspaceUnavailable` (all subclass `LifeOsError(Exception)`).
- Produces `FakeNotionClient` and `FakeCalendarClient` implementing the protocols defined in Tasks 8/9. Fakes are driven by in-memory dicts and can be told to raise a given error for a given ID (`fail_with={id: ErrorClass}`).

- [ ] **Step 1: Implement `errors.py`**

```python
class LifeOsError(Exception): ...
class NotionNotFound(LifeOsError): ...
class NotionAuthError(LifeOsError): ...
class TransientError(LifeOsError): ...
class WorkspaceUnavailable(LifeOsError): ...
```

- [ ] **Step 2: Implement `tests/fakes.py`**

```python
from lifeos_mcp.errors import NotionNotFound

class FakeNotionClient:
    """In-memory NotionClient. children: {parent_id: [child dicts]};
    pages: {id: page dict}; rows: {data_source_id: [row dicts]};
    fail_with: {id: ErrorClass} to simulate stale/auth/transient."""
    def __init__(self, children=None, pages=None, rows=None, child_db=None, fail_with=None):
        self.children = children or {}
        self.pages = pages or {}
        self.rows = rows or {}
        self.child_db = child_db or {}      # {page_id: data_source_id}
        self.fail_with = fail_with or {}
        self.created = []
    def _maybe_fail(self, oid):
        if oid in self.fail_with:
            raise self.fail_with[oid](oid)
    def get_block_children(self, block_id):
        self._maybe_fail(block_id)
        return self.children.get(block_id, [])
    def retrieve(self, object_id):
        self._maybe_fail(object_id)
        if object_id not in self.pages:
            raise NotionNotFound(object_id)
        return self.pages[object_id]
    def find_tasks_db_under(self, page_id):
        self._maybe_fail(page_id)
        return self.child_db.get(page_id)
    def query_data_source(self, data_source_id, filter=None, sorts=None):
        self._maybe_fail(data_source_id)
        return self.rows.get(data_source_id, [])
    def create_page(self, data_source_id, properties):
        rec = {"id": f"new-{len(self.created)}", "url": "http://n/new", "properties": properties}
        self.created.append((data_source_id, properties))
        return rec

class FakeCalendarClient:
    def __init__(self, events=None):
        self.events = events or []
        self.created = []
    def list_events(self, time_min, time_max):
        return self.events
    def create_event(self, title, start, end, notes=None):
        rec = {"id": f"ev-{len(self.created)}", "htmlLink": "http://cal/ev"}
        self.created.append((title, start, end, notes))
        return rec
```

- [ ] **Step 3: Verify import**

Run: `python -c "from tests.fakes import FakeNotionClient, FakeCalendarClient; print('ok')"`
Expected: `ok`.

- [ ] **Step 4: Commit**

```bash
git add lifeos-mcp/lifeos_mcp/errors.py lifeos-mcp/tests/fakes.py
git commit -m "feat(lifeos-mcp): error types + in-memory client fakes"
```

---

### Task 5: Resolver — schema lookup + done detection (rules C, D)

**Files:**
- Create: `lifeos-mcp/lifeos_mcp/resolver_schema.py`
- Test: `lifeos-mcp/tests/test_resolver_schema.py`

**Interfaces:**
- Consumes: a map dict; a source's `role_schemas[source_id]` (or `child_schema_defaults[role]`).
- Produces:
  - `schema_for(map, source_id, role) -> dict` — the source's property-role schema, falling back to `child_schema_defaults[role]`.
  - `prop(schema, prop_role) -> str | None` — real column name or `None` if absent (rule D).
  - `is_done(schema, props: dict) -> bool` — via `status_values.done` (compare the `status` select value) OR `done_when` `{property, equals}` (rule C). `props` is `{column_name: python_value}` already extracted.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_resolver_schema.py
from lifeos_mcp.resolver_schema import schema_for, prop, is_done
from tests.fixtures.maps import FIXTURE_MAP, ALT_MAP

def test_prop_present_and_absent():
    sch = schema_for(FIXTURE_MAP, "university_tasks_db", "tasks")
    assert prop(sch, "due_date") == "Due Date"
    assert prop(sch, "nonexistent") is None          # rule D

def test_is_done_via_status_value():
    sch = schema_for(FIXTURE_MAP, "university_tasks_db", "tasks")
    assert is_done(sch, {"Status": "Done"}) is True
    assert is_done(sch, {"Status": "Open"}) is False

def test_is_done_via_checkbox_predicate():
    sch = schema_for(ALT_MAP, "todo_db", "tasks")     # rule C: done_when
    assert is_done(sch, {"Erledigt": True}) is True
    assert is_done(sch, {"Erledigt": False}) is False

def test_child_schema_default_used_when_source_absent():
    sch = schema_for(FIXTURE_MAP, "some-enumerated-child-db", "tasks")
    assert prop(sch, "title") == "Name"               # falls back to child_schema_defaults
```

- [ ] **Step 2: Run to verify it fails**

Run: `pytest tests/test_resolver_schema.py -v`
Expected: FAIL (`ModuleNotFoundError`).

- [ ] **Step 3: Implement `resolver_schema.py`**

```python
def schema_for(map: dict, source_id: str, role: str) -> dict:
    schemas = map.get("role_schemas", {})
    if source_id in schemas:
        return schemas[source_id]
    return map.get("child_schema_defaults", {}).get(role, {})

def prop(schema: dict, prop_role: str) -> str | None:
    return schema.get(prop_role)  # rule D: absent -> None

def is_done(schema: dict, props: dict) -> bool:
    done_when = schema.get("done_when")
    if done_when:  # rule C: checkbox predicate
        return props.get(done_when["property"]) == done_when.get("equals", True)
    status_col = schema.get("status")
    done_val = (schema.get("status_values") or {}).get("done")
    if status_col and done_val is not None:
        return props.get(status_col) == done_val
    return False
```

- [ ] **Step 4: Run to verify it passes**

Run: `pytest tests/test_resolver_schema.py -v`
Expected: PASS (4 passed).

- [ ] **Step 5: Commit**

```bash
git add lifeos-mcp/lifeos_mcp/resolver_schema.py lifeos-mcp/tests/test_resolver_schema.py
git commit -m "feat(lifeos-mcp): schema lookup + done detection (rules C, D)"
```

---

### Task 6: Resolver — areas + source resolution with group enumeration

**Files:**
- Create: `lifeos-mcp/lifeos_mcp/resolver_areas.py`
- Test: `lifeos-mcp/tests/test_resolver_areas.py`

**Interfaces:**
- Consumes: map dict; a `NotionClient` (protocol, Task 8) — here exercised with `FakeNotionClient`.
- Produces:
  - `@dataclass ResolvedSource(source_id, role, area_key, area_label, area_emoji, schema)`.
  - `iter_areas(map) -> list[dict]` — area dicts `{key, label, emoji}` in map order.
  - `resolve_sources(map, client, role) -> list[ResolvedSource]` — for every area: anchored `sources` of `role` resolve directly; `group` areas enumerate children **cache-first** (use `resolved.groups[area]`), and on cache-miss enumerate `client.get_block_children(under)`, find each child's tasks DB via `client.find_tasks_db_under(child_id)`, **write back** `resolved.groups[area][child_id] = {label, role, tasks_db, cached_at}`. Children keyed by **ID** (rule i). Returns sources whose `role` matches.
  - `resolve_named(map, client, area_key, name) -> ResolvedSource | None` — case-insensitive/partial match on child `label`.
  - `today_str()` helper: `date.today().isoformat()` (clock injected by caller in tools; resolver uses a passed-in `today` arg where dates matter — see tools).

- [ ] **Step 1: Write the failing test**

```python
# tests/test_resolver_areas.py
import copy
from lifeos_mcp.resolver_areas import resolve_sources, iter_areas
from lifeos_mcp.errors import NotionNotFound
from tests.fixtures.maps import FIXTURE_MAP
from tests.fakes import FakeNotionClient

def test_iter_areas_order_and_labels():
    areas = iter_areas(FIXTURE_MAP)
    assert [a["label"] for a in areas] == ["Business", "University", "Work"]

def test_resolve_tasks_uses_cache_then_anchor():
    m = copy.deepcopy(FIXTURE_MAP)
    client = FakeNotionClient()  # no network needed; ventures already cached
    sources = resolve_sources(m, client, "tasks")
    ids = {s.source_id for s in sources}
    assert "uni-tasks" in ids                 # anchored university source
    assert "laundro-db" in ids                # cached venture tasks_db
    assert all(s.role == "tasks" for s in sources)

def test_resolve_tasks_enumerates_new_venture_and_writes_back():
    m = copy.deepcopy(FIXTURE_MAP)
    m["resolved"]["groups"]["ventures"] = {}   # force cache miss
    client = FakeNotionClient(
        children={"biz-root": [{"id": "van-page", "title": "Van Company"}]},
        child_db={"van-page": "van-db"},
    )
    sources = resolve_sources(m, client, "tasks")
    assert "van-db" in {s.source_id for s in sources}
    # write-back, keyed by ID, label stored
    assert m["resolved"]["groups"]["ventures"]["van-page"]["tasks_db"] == "van-db"
    assert m["resolved"]["groups"]["ventures"]["van-page"]["label"] == "Van Company"
```

- [ ] **Step 2: Run to verify it fails**

Run: `pytest tests/test_resolver_areas.py -v`
Expected: FAIL (`ModuleNotFoundError`).

- [ ] **Step 3: Implement `resolver_areas.py`**

```python
from dataclasses import dataclass
from datetime import date
from .resolver_schema import schema_for

@dataclass
class ResolvedSource:
    source_id: str; role: str; area_key: str
    area_label: str; area_emoji: str; schema: dict

def iter_areas(map: dict) -> list[dict]:
    return [{"key": k, "label": a.get("label", k), "emoji": a.get("emoji", "")}
            for k, a in map.get("areas", {}).items()]

def _anchor_id(map: dict, anchor: str) -> str:
    return map.get("anchors", {}).get(anchor, anchor)

def resolve_sources(map: dict, client, role: str) -> list[ResolvedSource]:
    out: list[ResolvedSource] = []
    for key, area in map.get("areas", {}).items():
        label, emoji = area.get("label", key), area.get("emoji", "")
        for src in area.get("sources", []):
            if src.get("role") != role:
                continue
            sid = _anchor_id(map, src["anchor"])
            out.append(ResolvedSource(sid, role, key, label, emoji,
                                      schema_for(map, sid, role)))
        group = area.get("group")
        if group and any(cs.get("role") == role for cs in group.get("child_sources", [])):
            for sid, label_ in _resolve_group(map, client, key, group, role):
                out.append(ResolvedSource(sid, role, key, label, emoji,
                                          schema_for(map, sid, role)))
    return out

def _resolve_group(map, client, area_key, group, role):
    cache = map.setdefault("resolved", {}).setdefault("groups", {}).setdefault(area_key, {})
    if not cache:  # cache miss -> enumerate once, write back (keyed by ID)
        ignored = set(map["resolved"].setdefault("ignored", []))
        tombstones = map["resolved"].setdefault("tombstones", {})
        for child in client.get_block_children(group["under"]):
            cid = child["id"]
            if cid in ignored or cid in tombstones:
                continue
            db = client.find_tasks_db_under(cid)
            if not db:
                ignored.add(cid); continue
            cache[cid] = {"label": child.get("title", cid), "role": role,
                          "tasks_db": db, "cached_at": date.today().isoformat()}
        map["resolved"]["ignored"] = sorted(ignored)
    for cid, entry in cache.items():
        if entry.get("role") == role:
            yield entry["tasks_db"], entry["label"]

def resolve_named(map, client, area_key, name):
    resolve_sources(map, client, "tasks")  # ensure enumerated
    cache = map["resolved"]["groups"].get(area_key, {})
    name_l = name.lower()
    for cid, entry in cache.items():
        if name_l in entry["label"].lower():
            return ResolvedSource(entry["tasks_db"], entry["role"], area_key,
                                  entry["label"], "", schema_for(map, entry["tasks_db"], entry["role"]))
    return None
```

- [ ] **Step 4: Run to verify it passes**

Run: `pytest tests/test_resolver_areas.py -v`
Expected: PASS (3 passed).

- [ ] **Step 5: Commit**

```bash
git add lifeos-mcp/lifeos_mcp/resolver_areas.py lifeos-mcp/tests/test_resolver_areas.py
git commit -m "feat(lifeos-mcp): area + group source resolution with write-back"
```

---

### Task 7: Resolver — stale handling (rules i–v)

**Files:**
- Create: `lifeos-mcp/lifeos_mcp/resolver_stale.py`
- Test: `lifeos-mcp/tests/test_resolver_stale.py`

**Interfaces:**
- Consumes: map dict; a `NotionClient`; errors from Task 4.
- Produces:
  - `classify_error(exc) -> str` — `"transient" | "auth" | "notfound"`.
  - `reconcile_group(map, client, area_key) -> dict` — re-enumerate a group with the blast-radius guard: match children by ID (rename → update `label`; missing-but-fetchable → drop membership; missing-and-NotFound → tombstone+drop). If **>1** child fetch raises auth/transient, raise `WorkspaceUnavailable` and **do not mutate** the cache (rules ii–iii). Returns a change summary `{renamed, dropped, tombstoned, added}`.
  - `drop_stale(map, source_id) -> None` — remove a single resolved entry by `tasks_db` id (used by tools on a confirmed single NotFound).

- [ ] **Step 1: Write the failing test**

```python
# tests/test_resolver_stale.py
import copy, pytest
from lifeos_mcp.resolver_stale import classify_error, reconcile_group
from lifeos_mcp.errors import NotionNotFound, NotionAuthError, TransientError, WorkspaceUnavailable
from tests.fixtures.maps import FIXTURE_MAP
from tests.fakes import FakeNotionClient

def test_classify():
    assert classify_error(TransientError("x")) == "transient"
    assert classify_error(NotionAuthError("x")) == "auth"
    assert classify_error(NotionNotFound("x")) == "notfound"

def test_rename_updates_label_not_membership():
    m = copy.deepcopy(FIXTURE_MAP)  # has venture laundro-page -> laundro-db
    client = FakeNotionClient(
        children={"biz-root": [{"id": "laundro-page", "title": "Laundromat Hannover GmbH"}]},
        child_db={"laundro-page": "laundro-db"},
    )
    summary = reconcile_group(m, client, "ventures")
    assert m["resolved"]["groups"]["ventures"]["laundro-page"]["label"] == "Laundromat Hannover GmbH"
    assert "laundro-page" in summary["renamed"]

def test_deleted_child_is_tombstoned():
    m = copy.deepcopy(FIXTURE_MAP)
    client = FakeNotionClient(children={"biz-root": []},
                              fail_with={"laundro-page": NotionNotFound})
    summary = reconcile_group(m, client, "ventures")
    assert "laundro-page" not in m["resolved"]["groups"]["ventures"]
    assert "laundro-page" in m["resolved"]["tombstones"]

def test_blast_radius_guard_raises_and_preserves_cache():
    m = copy.deepcopy(FIXTURE_MAP)
    m["resolved"]["groups"]["ventures"]["second-page"] = {
        "label": "Two", "role": "tasks", "tasks_db": "two-db", "cached_at": "2026-06-26"}
    client = FakeNotionClient(children={"biz-root": []},
        fail_with={"laundro-page": NotionAuthError, "second-page": NotionAuthError})
    before = copy.deepcopy(m["resolved"]["groups"]["ventures"])
    with pytest.raises(WorkspaceUnavailable):
        reconcile_group(m, client, "ventures")
    assert m["resolved"]["groups"]["ventures"] == before  # unchanged (rule iii)
```

- [ ] **Step 2: Run to verify it fails**

Run: `pytest tests/test_resolver_stale.py -v`
Expected: FAIL (`ModuleNotFoundError`).

- [ ] **Step 3: Implement `resolver_stale.py`**

```python
from datetime import date
from .errors import NotionNotFound, NotionAuthError, TransientError, WorkspaceUnavailable

def classify_error(exc) -> str:
    if isinstance(exc, TransientError): return "transient"
    if isinstance(exc, NotionAuthError): return "auth"
    if isinstance(exc, NotionNotFound): return "notfound"
    return "transient"

def reconcile_group(map: dict, client, area_key: str) -> dict:
    cache = map["resolved"]["groups"].setdefault(area_key, {})
    group = map["areas"][area_key]["group"]
    summary = {"renamed": [], "dropped": [], "tombstoned": [], "added": []}

    # current children under the anchor, by id
    present = {c["id"]: c for c in client.get_block_children(group["under"])}

    deletions, hard_failures = [], 0
    for cid, entry in list(cache.items()):
        if cid in present:
            new_label = present[cid].get("title", entry["label"])
            if new_label != entry["label"]:
                entry["label"] = new_label; summary["renamed"].append(cid)
            continue
        # not under the group anymore: is it deleted, or just moved/inaccessible?
        try:
            client.retrieve(cid)
            cache.pop(cid); summary["dropped"].append(cid)  # moved out of group
        except Exception as exc:
            kind = classify_error(exc)
            if kind == "notfound":
                deletions.append(cid)
            else:
                hard_failures += 1

    # blast-radius guard (rules ii–iii): >1 hard failure => connection/permission
    if hard_failures > 1:
        raise WorkspaceUnavailable(f"{hard_failures} children failed to resolve in {area_key}")

    for cid in deletions:
        entry = cache.pop(cid)
        map["resolved"]["tombstones"][cid] = {
            "reason": "deleted", "label": entry.get("label"), "seen_at": date.today().isoformat()}
        summary["tombstoned"].append(cid)

    # add genuinely new children
    ignored = set(map["resolved"].get("ignored", []))
    for cid, child in present.items():
        if cid in cache or cid in map["resolved"]["tombstones"] or cid in ignored:
            continue
        db = client.find_tasks_db_under(cid)
        if not db:
            ignored.add(cid); continue
        cache[cid] = {"label": child.get("title", cid), "role": "tasks",
                      "tasks_db": db, "cached_at": date.today().isoformat()}
        summary["added"].append(cid)
    map["resolved"]["ignored"] = sorted(ignored)
    return summary

def drop_stale(map: dict, source_id: str) -> None:
    for area in map["resolved"]["groups"].values():
        for cid, entry in list(area.items()):
            if entry.get("tasks_db") == source_id:
                area.pop(cid)
```

- [ ] **Step 4: Run to verify it passes**

Run: `pytest tests/test_resolver_stale.py -v`
Expected: PASS (4 passed).

- [ ] **Step 5: Commit**

```bash
git add lifeos-mcp/lifeos_mcp/resolver_stale.py lifeos-mcp/tests/test_resolver_stale.py
git commit -m "feat(lifeos-mcp): stale handling — classify, reconcile, blast-radius guard"
```

---

### Task 8: Notion client (protocol + httpx impl)

**Files:**
- Create: `lifeos-mcp/lifeos_mcp/notion_client.py`
- Test: `lifeos-mcp/tests/test_notion_client.py`

**Interfaces:**
- Produces a `NotionClient` Protocol with: `get_block_children(block_id) -> list[dict]` (each `{id, title}`), `retrieve(object_id) -> dict`, `find_tasks_db_under(page_id) -> str | None`, `query_data_source(data_source_id, filter=None, sorts=None) -> list[dict]`, `create_page(data_source_id, properties) -> dict`.
- Produces `HttpxNotionClient(token, api_version="2022-06-28")` implementing it; maps HTTP status → errors (`404`→`NotionNotFound`, `401/403`→`NotionAuthError`, `429/5xx`→`TransientError`).
- Produces helpers `extract_props(page) -> dict` (column→python value: title text, select name, checkbox bool, date start) and `build_props(schema, fields) -> dict` (python values → Notion property payloads), shared by tools.

- [ ] **Step 1: Write the failing test** (error mapping + extract are pure; HTTP is mocked)

```python
# tests/test_notion_client.py
import httpx, pytest
from lifeos_mcp.notion_client import HttpxNotionClient, extract_props
from lifeos_mcp.errors import NotionNotFound, NotionAuthError, TransientError

def _client(handler):
    transport = httpx.MockTransport(handler)
    c = HttpxNotionClient("tok")
    c._http = httpx.Client(transport=transport, base_url="https://api.notion.com")
    return c

def test_retrieve_404_maps_to_notfound():
    c = _client(lambda req: httpx.Response(404, json={"object": "error"}))
    with pytest.raises(NotionNotFound):
        c.retrieve("missing")

def test_retrieve_401_maps_to_auth():
    c = _client(lambda req: httpx.Response(401, json={}))
    with pytest.raises(NotionAuthError):
        c.retrieve("x")

def test_extract_props_reads_select_and_date():
    page = {"properties": {
        "Status": {"type": "select", "select": {"name": "Open"}},
        "Due Date": {"type": "date", "date": {"start": "2026-06-27"}},
        "Done?": {"type": "checkbox", "checkbox": True}}}
    props = extract_props(page)
    assert props["Status"] == "Open"
    assert props["Due Date"] == "2026-06-27"
    assert props["Done?"] is True
```

- [ ] **Step 2: Run to verify it fails**

Run: `pytest tests/test_notion_client.py -v`
Expected: FAIL (`ModuleNotFoundError`).

- [ ] **Step 3: Implement `notion_client.py`**

```python
from typing import Protocol
import httpx
from .errors import NotionNotFound, NotionAuthError, TransientError

class NotionClient(Protocol):
    def get_block_children(self, block_id: str) -> list[dict]: ...
    def retrieve(self, object_id: str) -> dict: ...
    def find_tasks_db_under(self, page_id: str) -> str | None: ...
    def query_data_source(self, data_source_id: str, filter=None, sorts=None) -> list[dict]: ...
    def create_page(self, data_source_id: str, properties: dict) -> dict: ...

def _raise_for_status(resp: httpx.Response):
    if resp.status_code == 404: raise NotionNotFound(resp.url.path)
    if resp.status_code in (401, 403): raise NotionAuthError(str(resp.status_code))
    if resp.status_code == 429 or resp.status_code >= 500: raise TransientError(str(resp.status_code))
    resp.raise_for_status()

def _title_of(page: dict) -> str:
    for v in page.get("properties", {}).values():
        if v.get("type") == "title":
            return "".join(t.get("plain_text", "") for t in v.get("title", []))
    return page.get("id", "")

def extract_props(page: dict) -> dict:
    out = {}
    for name, v in page.get("properties", {}).items():
        t = v.get("type")
        if t in ("select", "status"):
            out[name] = (v.get(t) or {}).get("name")
        elif t == "checkbox":
            out[name] = v.get("checkbox")
        elif t == "date":
            out[name] = (v.get("date") or {}).get("start")
        elif t == "title":
            out[name] = "".join(x.get("plain_text", "") for x in v.get("title", []))
        elif t == "rich_text":
            out[name] = "".join(x.get("plain_text", "") for x in v.get("rich_text", []))
    return out

def build_props(schema: dict, fields: dict) -> dict:
    """Map python field values -> Notion property payloads using the schema."""
    props = {}
    for role, value in fields.items():
        col = schema.get(role)
        if not col or value is None:
            continue
        if role == "title":
            props[col] = {"title": [{"text": {"content": str(value)}}]}
        elif role in ("status",):
            props[col] = {"select": {"name": str(value)}}
        elif role == "priority":
            props[col] = {"select": {"name": str(value)}}
        elif role in ("due_date", "exam_date"):
            props[col] = {"date": {"start": str(value)}}
        else:
            props[col] = {"rich_text": [{"text": {"content": str(value)}}]}
    return props

class HttpxNotionClient:
    def __init__(self, token: str, api_version: str = "2022-06-28"):
        self._http = httpx.Client(
            base_url="https://api.notion.com",
            headers={"Authorization": f"Bearer {token}",
                     "Notion-Version": api_version,
                     "Content-Type": "application/json"}, timeout=30.0)

    def get_block_children(self, block_id: str) -> list[dict]:
        r = self._http.get(f"/v1/blocks/{block_id}/children?page_size=100")
        _raise_for_status(r)
        out = []
        for b in r.json().get("results", []):
            if b.get("type") == "child_page":
                out.append({"id": b["id"], "title": b["child_page"]["title"]})
            elif b.get("type") == "child_database":
                out.append({"id": b["id"], "title": b["child_database"]["title"], "is_db": True})
        return out

    def retrieve(self, object_id: str) -> dict:
        r = self._http.get(f"/v1/pages/{object_id}")
        if r.status_code == 404:
            r = self._http.get(f"/v1/databases/{object_id}")
        _raise_for_status(r)
        return r.json()

    def find_tasks_db_under(self, page_id: str) -> str | None:
        for child in self.get_block_children(page_id):
            if child.get("is_db"):
                return child["id"]
        return None

    def query_data_source(self, data_source_id: str, filter=None, sorts=None) -> list[dict]:
        body = {}
        if filter: body["filter"] = filter
        if sorts: body["sorts"] = sorts
        r = self._http.post(f"/v1/databases/{data_source_id}/query", json=body)
        _raise_for_status(r)
        return r.json().get("results", [])

    def create_page(self, data_source_id: str, properties: dict) -> dict:
        r = self._http.post("/v1/pages",
                            json={"parent": {"database_id": data_source_id}, "properties": properties})
        _raise_for_status(r)
        return r.json()
```

> **Note (Notion API):** newer Notion exposes "data sources" under databases. v1 targets the classic `/v1/databases/{id}/query` + `database_id` parent, which the existing workspace uses. If the live workspace requires the data-source endpoints, adjust only this file — the protocol and all callers are unchanged.

- [ ] **Step 4: Run to verify it passes**

Run: `pytest tests/test_notion_client.py -v`
Expected: PASS (3 passed).

- [ ] **Step 5: Commit**

```bash
git add lifeos-mcp/lifeos_mcp/notion_client.py lifeos-mcp/tests/test_notion_client.py
git commit -m "feat(lifeos-mcp): Notion REST client + prop extract/build + error mapping"
```

---

### Task 9: Calendar client (protocol + Google impl)

**Files:**
- Create: `lifeos-mcp/lifeos_mcp/calendar_client.py`
- Test: `lifeos-mcp/tests/test_calendar_client.py`

**Interfaces:**
- Produces a `CalendarClient` Protocol: `list_events(time_min: str, time_max: str) -> list[dict]` (each `{id, title, start, end}`), `create_event(title, start, end, notes=None) -> dict`.
- Produces `GoogleCalendarClient(credentials_path, token_path, tz="Europe/Berlin")` implementing it via `google-api-python-client`, reusing the cached OAuth token written by `@cocal/google-calendar-mcp`.
- Produces a pure helper `normalize_event(raw: dict) -> dict` (Google event → `{id, title, start, end}`), unit-tested without Google.

- [ ] **Step 1: Write the failing test** (only the pure normalizer)

```python
# tests/test_calendar_client.py
from lifeos_mcp.calendar_client import normalize_event

def test_normalize_timed_event():
    raw = {"id": "e1", "summary": "Lecture",
           "start": {"dateTime": "2026-06-27T10:00:00+02:00"},
           "end": {"dateTime": "2026-06-27T12:00:00+02:00"}}
    assert normalize_event(raw) == {"id": "e1", "title": "Lecture",
        "start": "2026-06-27T10:00:00+02:00", "end": "2026-06-27T12:00:00+02:00"}

def test_normalize_all_day_event():
    raw = {"id": "e2", "summary": "Holiday",
           "start": {"date": "2026-06-27"}, "end": {"date": "2026-06-28"}}
    assert normalize_event(raw)["start"] == "2026-06-27"
```

- [ ] **Step 2: Run to verify it fails**

Run: `pytest tests/test_calendar_client.py -v`
Expected: FAIL (`ModuleNotFoundError`).

- [ ] **Step 3: Implement `calendar_client.py`**

```python
from typing import Protocol

class CalendarClient(Protocol):
    def list_events(self, time_min: str, time_max: str) -> list[dict]: ...
    def create_event(self, title: str, start: str, end: str, notes=None) -> dict: ...

def normalize_event(raw: dict) -> dict:
    def _se(side): return side.get("dateTime") or side.get("date")
    return {"id": raw.get("id"), "title": raw.get("summary", ""),
            "start": _se(raw.get("start", {})), "end": _se(raw.get("end", {}))}

class GoogleCalendarClient:
    def __init__(self, credentials_path: str, token_path: str, tz: str = "Europe/Berlin"):
        from google.oauth2.credentials import Credentials
        from googleapiclient.discovery import build
        creds = Credentials.from_authorized_user_file(
            token_path, ["https://www.googleapis.com/auth/calendar"])
        self._svc = build("calendar", "v3", credentials=creds, cache_discovery=False)
        self._tz = tz

    def list_events(self, time_min: str, time_max: str) -> list[dict]:
        resp = self._svc.events().list(calendarId="primary", timeMin=time_min,
            timeMax=time_max, singleEvents=True, orderBy="startTime").execute()
        return [normalize_event(e) for e in resp.get("items", [])]

    def create_event(self, title: str, start: str, end: str, notes=None) -> dict:
        body = {"summary": title, "description": notes or "",
                "start": {"dateTime": start, "timeZone": self._tz},
                "end": {"dateTime": end, "timeZone": self._tz}}
        ev = self._svc.events().insert(calendarId="primary", body=body).execute()
        return {"id": ev["id"], "htmlLink": ev.get("htmlLink")}
```

- [ ] **Step 4: Run to verify it passes**

Run: `pytest tests/test_calendar_client.py -v`
Expected: PASS (2 passed).

- [ ] **Step 5: Commit**

```bash
git add lifeos-mcp/lifeos_mcp/calendar_client.py lifeos-mcp/tests/test_calendar_client.py
git commit -m "feat(lifeos-mcp): Google Calendar client + event normalizer"
```

---

### Task 10: Tool — get_today

**Files:**
- Create: `lifeos-mcp/lifeos_mcp/tools/__init__.py`
- Create: `lifeos-mcp/lifeos_mcp/tools/get_today.py`
- Test: `lifeos-mcp/tests/test_tools_today.py`

**Interfaces:**
- Consumes: map dict, `NotionClient`, `CalendarClient`, `today: date`, `tz`.
- Produces: `get_today(map, notion, calendar, today) -> TodayPayload`. Builds one `AreaBlock` per area: `tasks` = rows across that area's `tasks` sources where `due_date <= today` and not `is_done`; `exams` = rows with an `exam_date`; `shift` = a `schedule` row with `date == today`. `events` from `calendar.list_events` for today. Per-source failure → append to `warnings`, continue (partial-failure rule). Tools convert Notion rows via `extract_props` then schema `prop(...)`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_tools_today.py
import copy
from datetime import date
from lifeos_mcp.tools.get_today import get_today
from tests.fixtures.maps import FIXTURE_MAP
from tests.fakes import FakeNotionClient, FakeCalendarClient

def _row(title, status, due):
    return {"id": title, "url": f"http://n/{title}",
            "properties": {"Name": {"type": "title", "title": [{"plain_text": title}]},
                           "Status": {"type": "select", "select": {"name": status}},
                           "Due Date": {"type": "date", "date": {"start": due}}}}

def test_today_aggregates_tasks_due_and_open():
    m = copy.deepcopy(FIXTURE_MAP)
    notion = FakeNotionClient(rows={
        "uni-tasks": [_row("Essay", "Open", "2026-06-27"), _row("OldDone", "Done", "2026-06-01")],
        "laundro-db": [_row("Call landlord", "Open", "2026-06-26")]})
    cal = FakeCalendarClient(events=[{"id":"e","title":"Standup","start":"x","end":"y"}])
    payload = get_today(m, notion, cal, date(2026, 6, 27))
    titles = {t.title for a in payload.areas for t in a.tasks}
    assert "Essay" in titles and "Call landlord" in titles
    assert "OldDone" not in titles            # done filtered out
    assert len(payload.events) == 1

def test_today_partial_failure_warns_not_aborts():
    from lifeos_mcp.errors import TransientError
    m = copy.deepcopy(FIXTURE_MAP)
    notion = FakeNotionClient(rows={"uni-tasks": [_row("Essay","Open","2026-06-27")]},
                              fail_with={"laundro-db": TransientError})
    cal = FakeCalendarClient()
    payload = get_today(m, notion, cal, date(2026, 6, 27))
    assert any("laundro-db" in w for w in payload.warnings)
    assert any(t.title == "Essay" for a in payload.areas for t in a.tasks)
```

- [ ] **Step 2: Run to verify it fails**

Run: `pytest tests/test_tools_today.py -v`
Expected: FAIL (`ModuleNotFoundError`).

- [ ] **Step 3: Implement `tools/get_today.py`** (create empty `tools/__init__.py` too)

```python
from datetime import date
from ..models import TaskRecord, ScheduleRecord, EventRecord, AreaBlock, TodayPayload
from ..resolver_areas import resolve_sources, iter_areas
from ..resolver_schema import prop, is_done
from ..notion_client import extract_props

def _to_date(s):
    return date.fromisoformat(s[:10]) if s else None

def _task_rows(map, notion, source, today, warnings):
    tasks, exams = [], []
    try:
        rows = notion.query_data_source(source.source_id)
    except Exception as exc:
        warnings.append(f"task source {source.source_id} failed: {exc}")
        return tasks, exams
    sch = source.schema
    for row in rows:
        props = extract_props(row)
        if is_done(sch, props):
            continue
        due = _to_date(props.get(prop(sch, "due_date"))) if prop(sch, "due_date") else None
        exam = _to_date(props.get(prop(sch, "exam_date"))) if prop(sch, "exam_date") else None
        title = props.get(prop(sch, "title")) or ""
        rec = TaskRecord(id=row.get("id",""), title=title,
            status=props.get(prop(sch,"status")) if prop(sch,"status") else None,
            priority=props.get(prop(sch,"priority")) if prop(sch,"priority") else None,
            due_date=due, exam_date=exam, area_label=source.area_label,
            source_id=source.source_id, overdue=bool(due and due < today),
            url=row.get("url"))
        if exam:
            exams.append(rec)
        if due and due <= today:
            tasks.append(rec)
    return tasks, exams

def _shift(map, notion, source, today, warnings):
    try:
        rows = notion.query_data_source(source.source_id)
    except Exception as exc:
        warnings.append(f"schedule source {source.source_id} failed: {exc}")
        return None
    sch = source.schema
    for row in rows:
        props = extract_props(row)
        d = _to_date(props.get(prop(sch, "date"))) if prop(sch, "date") else None
        if d == today:
            return ScheduleRecord(id=row.get("id",""), title=props.get(prop(sch,"title")) or "",
                date=d, start=props.get(prop(sch,"start")) if prop(sch,"start") else None,
                end=props.get(prop(sch,"end")) if prop(sch,"end") else None,
                source_id=source.source_id)
    return None

def get_today(map, notion, calendar, today: date) -> TodayPayload:
    warnings: list[str] = []
    task_sources = resolve_sources(map, notion, "tasks")
    sched_sources = resolve_sources(map, notion, "schedule")
    blocks = []
    for area in iter_areas(map):
        a_tasks, a_exams, a_shift = [], [], None
        for s in (s for s in task_sources if s.area_key == area["key"]):
            ts, es = _task_rows(map, notion, s, today, warnings)
            a_tasks += ts; a_exams += es
        for s in (s for s in sched_sources if s.area_key == area["key"]):
            a_shift = a_shift or _shift(map, notion, s, today, warnings)
        if a_tasks or a_exams or a_shift:
            blocks.append(AreaBlock(area["label"], area["emoji"], a_tasks, a_exams, a_shift))
    events = []
    try:
        tmin, tmax = f"{today.isoformat()}T00:00:00Z", f"{today.isoformat()}T23:59:59Z"
        events = [EventRecord(**e) for e in calendar.list_events(tmin, tmax)]
    except Exception as exc:
        warnings.append(f"calendar failed: {exc}")
    return TodayPayload(date=today, areas=blocks, events=events, warnings=warnings)
```

- [ ] **Step 4: Run to verify it passes**

Run: `pytest tests/test_tools_today.py -v`
Expected: PASS (2 passed).

- [ ] **Step 5: Commit**

```bash
git add lifeos-mcp/lifeos_mcp/tools/__init__.py lifeos-mcp/lifeos_mcp/tools/get_today.py lifeos-mcp/tests/test_tools_today.py
git commit -m "feat(lifeos-mcp): get_today tool"
```

---

### Task 11: Tool — get_week

**Files:**
- Create: `lifeos-mcp/lifeos_mcp/tools/get_week.py`
- Test: `lifeos-mcp/tests/test_tools_week.py`

**Interfaces:**
- Produces: `get_week(map, notion, calendar, today: date) -> WeekPayload`. Computes Mon–Sun containing `today`. Tasks/exams with `due_date`/`exam_date` in range and not done; business tasks also included when `status == status_values.this_week` (if declared). Shifts with `date` in range. Events for the week. `days` is a list of `{date, tasks, exams, shift, events}` dicts; empty days omitted. `summary` = counts. Reuses helpers from `get_today` via a shared `_in_range`/`extract` path.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_tools_week.py
import copy
from datetime import date
from lifeos_mcp.tools.get_week import get_week, week_bounds
from tests.fixtures.maps import FIXTURE_MAP
from tests.fakes import FakeNotionClient, FakeCalendarClient

def test_week_bounds_monday_sunday():
    start, end = week_bounds(date(2026, 6, 27))  # Saturday
    assert start == date(2026, 6, 22) and end == date(2026, 6, 28)

def test_week_includes_in_range_open_tasks():
    m = copy.deepcopy(FIXTURE_MAP)
    row = {"id": "t1", "url": "u", "properties": {
        "Name": {"type":"title","title":[{"plain_text":"Exam prep"}]},
        "Status": {"type":"select","select":{"name":"Open"}},
        "Due Date": {"type":"date","date":{"start":"2026-06-25"}}}}
    notion = FakeNotionClient(rows={"uni-tasks": [row]})
    payload = get_week(m, notion, FakeCalendarClient(), date(2026, 6, 27))
    assert payload.summary["tasks"] >= 1
```

- [ ] **Step 2: Run to verify it fails**

Run: `pytest tests/test_tools_week.py -v`
Expected: FAIL (`ModuleNotFoundError`).

- [ ] **Step 3: Implement `tools/get_week.py`**

```python
from datetime import date, timedelta
from ..models import EventRecord, WeekPayload
from ..resolver_areas import resolve_sources
from ..resolver_schema import prop, is_done
from ..notion_client import extract_props
from .get_today import _to_date

def week_bounds(today: date) -> tuple[date, date]:
    start = today - timedelta(days=today.weekday())  # Monday
    return start, start + timedelta(days=6)

def get_week(map, notion, calendar, today: date) -> WeekPayload:
    start, end = week_bounds(today)
    warnings: list[str] = []
    buckets: dict[str, dict] = {}
    def bucket(d): return buckets.setdefault(d.isoformat(),
        {"date": d.isoformat(), "tasks": [], "exams": [], "shift": None, "events": []})

    for s in resolve_sources(map, notion, "tasks"):
        try:
            rows = notion.query_data_source(s.source_id)
        except Exception as exc:
            warnings.append(f"task source {s.source_id} failed: {exc}"); continue
        sch = s.schema
        tw = (sch.get("status_values") or {}).get("this_week")
        for row in rows:
            props = extract_props(row)
            if is_done(sch, props): continue
            due = _to_date(props.get(prop(sch,"due_date"))) if prop(sch,"due_date") else None
            exam = _to_date(props.get(prop(sch,"exam_date"))) if prop(sch,"exam_date") else None
            title = props.get(prop(sch,"title")) or ""
            status = props.get(prop(sch,"status")) if prop(sch,"status") else None
            item = {"title": title, "area": s.area_label, "status": status,
                    "due_date": due.isoformat() if due else None}
            if exam and start <= exam <= end: bucket(exam)["exams"].append(item)
            if due and start <= due <= end: bucket(due)["tasks"].append(item)
            elif tw and status == tw: bucket(start)["tasks"].append(item)

    for s in resolve_sources(map, notion, "schedule"):
        try:
            rows = notion.query_data_source(s.source_id)
        except Exception as exc:
            warnings.append(f"schedule {s.source_id} failed: {exc}"); continue
        sch = s.schema
        for row in rows:
            props = extract_props(row)
            d = _to_date(props.get(prop(sch,"date"))) if prop(sch,"date") else None
            if d and start <= d <= end:
                bucket(d)["shift"] = {"title": props.get(prop(sch,"title")) or "",
                    "start": props.get(prop(sch,"start")) if prop(sch,"start") else None,
                    "end": props.get(prop(sch,"end")) if prop(sch,"end") else None}

    try:
        evs = calendar.list_events(f"{start.isoformat()}T00:00:00Z", f"{end.isoformat()}T23:59:59Z")
        for e in evs:
            d = _to_date(e["start"])
            if d: bucket(d)["events"].append(EventRecord(**e).to_dict())
    except Exception as exc:
        warnings.append(f"calendar failed: {exc}")

    days = [buckets[k] for k in sorted(buckets)]
    summary = {"tasks": sum(len(d["tasks"]) for d in days),
               "exams": sum(len(d["exams"]) for d in days),
               "shifts": sum(1 for d in days if d["shift"])}
    return WeekPayload(start=start, end=end, days=days, summary=summary, warnings=warnings)
```

- [ ] **Step 4: Run to verify it passes**

Run: `pytest tests/test_tools_week.py -v`
Expected: PASS (2 passed).

- [ ] **Step 5: Commit**

```bash
git add lifeos-mcp/lifeos_mcp/tools/get_week.py lifeos-mcp/tests/test_tools_week.py
git commit -m "feat(lifeos-mcp): get_week tool"
```

---

### Task 12: Tool — query_records

**Files:**
- Create: `lifeos-mcp/lifeos_mcp/tools/query_records.py`
- Test: `lifeos-mcp/tests/test_tools_query.py`

**Interfaces:**
- Produces: `query_records(map, notion, role: str, filters: dict | None = None) -> list[dict]`. Resolves all sources of `role`; applies in-memory filters mapped via the schema: `status` (exact), `area` (area_label match), `due_before`/`due_after` (date compare), `not_done` (bool, uses `is_done`). Returns flat list of record dicts `{id, title, status, due_date, area, source_id, url}`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_tools_query.py
import copy
from lifeos_mcp.tools.query_records import query_records
from tests.fixtures.maps import FIXTURE_MAP
from tests.fakes import FakeNotionClient

def _row(title, status, due):
    return {"id": title, "url": "u", "properties": {
        "Name": {"type":"title","title":[{"plain_text": title}]},
        "Status": {"type":"select","select":{"name": status}},
        "Due Date": {"type":"date","date":{"start": due}}}}

def test_query_filters_by_status_and_area():
    m = copy.deepcopy(FIXTURE_MAP)
    notion = FakeNotionClient(rows={
        "uni-tasks": [_row("A","Open","2026-07-01")],
        "laundro-db": [_row("B","Backlog","2026-07-02"), _row("C","Open","2026-07-03")]})
    res = query_records(m, notion, "tasks", {"status": "Open", "area": "Business"})
    assert [r["title"] for r in res] == ["C"]
```

- [ ] **Step 2: Run to verify it fails**

Run: `pytest tests/test_tools_query.py -v`
Expected: FAIL.

- [ ] **Step 3: Implement `tools/query_records.py`**

```python
from datetime import date
from ..resolver_areas import resolve_sources
from ..resolver_schema import prop, is_done
from ..notion_client import extract_props
from .get_today import _to_date

def query_records(map, notion, role: str, filters: dict | None = None) -> list[dict]:
    filters = filters or {}
    out = []
    for s in resolve_sources(map, notion, role):
        if filters.get("area") and filters["area"].lower() not in s.area_label.lower():
            continue
        sch = s.schema
        try:
            rows = notion.query_data_source(s.source_id)
        except Exception:
            continue
        for row in rows:
            props = extract_props(row)
            status = props.get(prop(sch, "status")) if prop(sch, "status") else None
            due = _to_date(props.get(prop(sch, "due_date"))) if prop(sch, "due_date") else None
            if filters.get("not_done") and is_done(sch, props): continue
            if filters.get("status") and status != filters["status"]: continue
            if filters.get("due_before") and not (due and due < date.fromisoformat(filters["due_before"])): continue
            if filters.get("due_after") and not (due and due > date.fromisoformat(filters["due_after"])): continue
            out.append({"id": row.get("id",""), "title": props.get(prop(sch,"title")) or "",
                        "status": status, "due_date": due.isoformat() if due else None,
                        "area": s.area_label, "source_id": s.source_id, "url": row.get("url")})
    return out
```

- [ ] **Step 4: Run to verify it passes**

Run: `pytest tests/test_tools_query.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add lifeos-mcp/lifeos_mcp/tools/query_records.py lifeos-mcp/tests/test_tools_query.py
git commit -m "feat(lifeos-mcp): query_records tool"
```

---

### Task 13: Tools — add_record + create_event

**Files:**
- Create: `lifeos-mcp/lifeos_mcp/tools/add_record.py`
- Create: `lifeos-mcp/lifeos_mcp/tools/create_event.py`
- Test: `lifeos-mcp/tests/test_tools_add.py`

**Interfaces:**
- Produces:
  - `add_record(map, notion, role: str, fields: dict, area: str | None = None) -> dict` — resolves destination: if `area` names a group child, use `resolve_named`; else the single anchored source of `role`. Applies defaults (`status` from `status_values` start if absent? — only set `priority="Medium"` if the schema has a `priority` column and none given). Builds Notion props via `build_props(schema, fields)`. Calls `notion.create_page`. Returns `{created: True, id, url, destination}`. Never creates structures.
  - `create_event(calendar, title, start, end=None, notes=None, default_minutes=60) -> dict` — computes `end` if absent (+1h), calls `calendar.create_event`. Returns `{created: True, id, link}`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_tools_add.py
import copy
from lifeos_mcp.tools.add_record import add_record
from lifeos_mcp.tools.create_event import create_event
from tests.fixtures.maps import FIXTURE_MAP
from tests.fakes import FakeNotionClient, FakeCalendarClient

def test_add_task_to_named_business_uses_schema_columns():
    m = copy.deepcopy(FIXTURE_MAP)
    notion = FakeNotionClient()
    res = add_record(m, notion, "tasks", {"title": "Order soap", "due_date": "2026-07-01"},
                     area="Laundromat")
    assert res["created"] is True
    db, props = notion.created[-1]
    assert db == "laundro-db"
    assert "Name" in props and props["Name"]["title"][0]["text"]["content"] == "Order soap"

def test_add_university_task_to_anchor():
    m = copy.deepcopy(FIXTURE_MAP)
    notion = FakeNotionClient()
    res = add_record(m, notion, "tasks", {"title": "Read ch.3"})
    assert notion.created[-1][0] in ("uni-tasks", "laundro-db")  # an anchored/known tasks db

def test_create_event_defaults_one_hour():
    cal = FakeCalendarClient()
    res = create_event(cal, "Call", "2026-06-27T10:00:00+02:00")
    assert res["created"] is True
    title, start, end, notes = cal.created[-1]
    assert end == "2026-06-27T11:00:00+02:00"
```

- [ ] **Step 2: Run to verify it fails**

Run: `pytest tests/test_tools_add.py -v`
Expected: FAIL.

- [ ] **Step 3: Implement both tools**

```python
# tools/add_record.py
from ..resolver_areas import resolve_sources, resolve_named
from ..resolver_schema import schema_for, prop
from ..notion_client import build_props

def add_record(map, notion, role: str, fields: dict, area: str | None = None) -> dict:
    target = None
    if area:
        # try a named group child first, then an anchored source whose area matches
        for akey, a in map.get("areas", {}).items():
            if area.lower() in a.get("label", "").lower() and "group" in a:
                target = resolve_named(map, notion, akey, area) or resolve_named(map, notion, akey, a["label"])
                break
        if target is None:
            named = None
            for akey in map.get("areas", {}):
                named = resolve_named(map, notion, akey, area)
                if named: break
            target = named
    if target is None:
        sources = resolve_sources(map, notion, role)
        if not sources:
            return {"created": False, "error": f"no source for role {role}"}
        target = sources[0]
    sch = target.schema
    fields = dict(fields)
    if prop(sch, "priority") and "priority" not in fields:
        fields["priority"] = "Medium"
    props = build_props(sch, fields)
    page = notion.create_page(target.source_id, props)
    return {"created": True, "id": page.get("id"), "url": page.get("url"),
            "destination": target.area_label}
```

```python
# tools/create_event.py
from datetime import datetime, timedelta

def create_event(calendar, title: str, start: str, end: str | None = None,
                 notes: str | None = None, default_minutes: int = 60) -> dict:
    if not end:
        dt = datetime.fromisoformat(start)
        end = (dt + timedelta(minutes=default_minutes)).isoformat()
    ev = calendar.create_event(title, start, end, notes)
    return {"created": True, "id": ev.get("id"), "link": ev.get("htmlLink")}
```

- [ ] **Step 4: Run to verify it passes**

Run: `pytest tests/test_tools_add.py -v`
Expected: PASS (3 passed).

- [ ] **Step 5: Commit**

```bash
git add lifeos-mcp/lifeos_mcp/tools/add_record.py lifeos-mcp/lifeos_mcp/tools/create_event.py lifeos-mcp/tests/test_tools_add.py
git commit -m "feat(lifeos-mcp): add_record + create_event tools"
```

---

### Task 14: Server wiring (FastMCP)

**Files:**
- Create: `lifeos-mcp/lifeos_mcp/server.py`
- Test: `lifeos-mcp/tests/test_server.py`

**Interfaces:**
- Produces a FastMCP app exposing five tools that load the map, build real clients from `Settings`, call the Task 10–13 functions with `today = datetime.now(ZoneInfo(tz)).date()`, **save the map** after resolution write-backs, and return `payload.to_dict()` / list / dict. Each tool catches `WorkspaceUnavailable` → returns `{error: "reconnect_notion"}`. Exposes `build_app(settings, notion=None, calendar=None) -> FastMCP` (clients injectable for tests) and `main()` running `app.run()` over stdio.

- [ ] **Step 1: Write the failing test** (build the app with fakes; assert tools registered + today runs)

```python
# tests/test_server.py
import copy
from datetime import date
from lifeos_mcp.server import build_app
from lifeos_mcp.config import Settings
from tests.fixtures.maps import FIXTURE_MAP
from tests.fakes import FakeNotionClient, FakeCalendarClient

def test_app_registers_five_tools(tmp_path):
    import json
    mp = tmp_path / "m.json"; mp.write_text(json.dumps(FIXTURE_MAP), encoding="utf-8")
    s = Settings(map_path=mp, notion_token="t", google_credentials="", google_token_path="")
    app = build_app(s, notion=FakeNotionClient(), calendar=FakeCalendarClient())
    names = {t.name for t in app._tool_manager.list_tools()}  # FastMCP registry
    assert {"get_today","get_week","query_records","add_record","create_event"} <= names
```

> If the installed FastMCP exposes tools differently, assert via `app.list_tools()`/the documented accessor; the point is all five names are registered.

- [ ] **Step 2: Run to verify it fails**

Run: `pytest tests/test_server.py -v`
Expected: FAIL (`ModuleNotFoundError`).

- [ ] **Step 3: Implement `server.py`**

```python
from datetime import datetime
from zoneinfo import ZoneInfo
from mcp.server.fastmcp import FastMCP
from .config import Settings, load_settings, load_map, save_map
from .errors import WorkspaceUnavailable
from .notion_client import HttpxNotionClient
from .calendar_client import GoogleCalendarClient
from .tools.get_today import get_today
from .tools.get_week import get_week
from .tools.query_records import query_records
from .tools.add_record import add_record
from .tools.create_event import create_event

def build_app(settings: Settings, notion=None, calendar=None) -> FastMCP:
    app = FastMCP("lifeos")
    def _notion():
        return notion or HttpxNotionClient(settings.notion_token)
    def _calendar():
        return calendar or GoogleCalendarClient(settings.google_credentials, settings.google_token_path, settings.tz)
    def _today():
        return datetime.now(ZoneInfo(settings.tz)).date()

    @app.tool()
    def get_today_tool() -> dict:
        """Today's tasks, exams, work shift, and calendar events across all areas."""
        m = load_map(settings.map_path)
        try:
            payload = get_today(m, _notion(), _calendar(), _today())
        except WorkspaceUnavailable:
            return {"error": "reconnect_notion"}
        save_map(m, settings.map_path)
        return payload.to_dict()

    @app.tool()
    def get_week_tool() -> dict:
        """This week's tasks, deadlines, shifts, and events (Mon–Sun)."""
        m = load_map(settings.map_path)
        try:
            payload = get_week(m, _notion(), _calendar(), _today())
        except WorkspaceUnavailable:
            return {"error": "reconnect_notion"}
        save_map(m, settings.map_path)
        return payload.to_dict()

    @app.tool()
    def query_records_tool(role: str, filters: dict | None = None) -> list:
        """Query records of a function role (tasks/schedule/catalog) with optional filters."""
        m = load_map(settings.map_path)
        res = query_records(m, _notion(), role, filters)
        save_map(m, settings.map_path)
        return res

    @app.tool()
    def add_record_tool(role: str, fields: dict, area: str | None = None) -> dict:
        """Create a record (row) of a role into its resolved destination. Records only."""
        m = load_map(settings.map_path)
        res = add_record(m, _notion(), role, fields, area)
        save_map(m, settings.map_path)
        return res

    @app.tool()
    def create_event_tool(title: str, start: str, end: str | None = None, notes: str | None = None) -> dict:
        """Create a Google Calendar event (Europe/Berlin, default 1h)."""
        return create_event(_calendar(), title, start, end, notes)

    # expose clean tool names
    for fn, name in [(get_today_tool,"get_today"),(get_week_tool,"get_week"),
                     (query_records_tool,"query_records"),(add_record_tool,"add_record"),
                     (create_event_tool,"create_event")]:
        pass  # names set via decorator below in Step 3b
    return app

def main():
    build_app(load_settings()).run()

if __name__ == "__main__":
    main()
```

- [ ] **Step 3b: Set explicit tool names**

Change each decorator to name the tool explicitly so the registry matches the test and the agent's `allowed_tools`: `@app.tool(name="get_today")`, `@app.tool(name="get_week")`, `@app.tool(name="query_records")`, `@app.tool(name="add_record")`, `@app.tool(name="create_event")`. Remove the dead `for ... pass` loop.

- [ ] **Step 4: Run to verify it passes**

Run: `pytest tests/test_server.py -v`
Expected: PASS. If the FastMCP registry accessor differs in the installed version, adjust the test's accessor (Step 1 note) until it lists the five names.

- [ ] **Step 5: Run the full suite**

Run: `pytest -v`
Expected: all tests pass.

- [ ] **Step 6: Commit**

```bash
git add lifeos-mcp/lifeos_mcp/server.py lifeos-mcp/tests/test_server.py
git commit -m "feat(lifeos-mcp): FastMCP server wiring for five tools"
```

---

### Task 15: Portability (map-swap) test

**Files:**
- Create: `lifeos-mcp/tests/test_portability.py`

**Interfaces:**
- Consumes: `ALT_MAP` (Task 3), tools, fakes. Produces no code — proves the same tools run on a differently-shaped map (different labels, German columns, checkbox-done) with no code change.

- [ ] **Step 1: Write the test**

```python
# tests/test_portability.py
import copy
from datetime import date
from lifeos_mcp.tools.get_today import get_today
from tests.fixtures.maps import ALT_MAP
from tests.fakes import FakeNotionClient, FakeCalendarClient

def test_alt_map_today_uses_german_columns_and_checkbox_done():
    m = copy.deepcopy(ALT_MAP)
    row_open = {"id":"r1","url":"u","properties":{
        "Titel":{"type":"title","title":[{"plain_text":"Rechnung zahlen"}]},
        "Fällig":{"type":"date","date":{"start":"2026-06-27"}},
        "Erledigt":{"type":"checkbox","checkbox":False}}}
    row_done = {"id":"r2","url":"u","properties":{
        "Titel":{"type":"title","title":[{"plain_text":"Fertig"}]},
        "Fällig":{"type":"date","date":{"start":"2026-06-20"}},
        "Erledigt":{"type":"checkbox","checkbox":True}}}
    notion = FakeNotionClient(rows={"todo-db": [row_open, row_done]})
    payload = get_today(m, notion, FakeCalendarClient(), date(2026, 6, 27))
    titles = {t.title for a in payload.areas for t in a.tasks}
    assert "Rechnung zahlen" in titles      # German due column resolved
    assert "Fertig" not in titles           # checkbox-done filtered (rule C)
    assert any(a.label == "Persönlich" for a in payload.areas)  # map-driven label
```

- [ ] **Step 2: Run to verify it passes**

Run: `pytest tests/test_portability.py -v`
Expected: PASS.

- [ ] **Step 3: Commit**

```bash
git add lifeos-mcp/tests/test_portability.py
git commit -m "test(lifeos-mcp): map-swap portability proof"
```

---

### Task 16: No-hardcoded-ID gate (Phase A close-out)

**Files:** none (verification only)

- [ ] **Step 1: Grep the package for IDs/raw columns**

Run:
```bash
rg -nE "[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}|[0-9a-f]{32}" lifeos-mcp/lifeos_mcp; echo "exit:$?"
```
Expected: **no output**, non-zero exit (test fixtures under `lifeos-mcp/tests` are allowed to contain synthetic IDs; production code must not).

- [ ] **Step 2: Full suite green**

Run: `pytest -v` (from `lifeos-mcp/`)
Expected: all pass.

- [ ] **Step 3: No commit** (verification only). Phase A done — the server is independently working and tested.

---

## PHASE B — Integration & migration (touches existing behavior)

### Task 17: Migrate the real `context/lifeos.map.json`

**Files:**
- Modify: `context/lifeos.map.json`

**Interfaces:**
- Produces the live map in the new shape: `anchors` (unchanged real IDs), `areas` (ventures/university/work), `role_schemas` (from the current schemas), `child_schema_defaults.tasks` (the business-tasks schema), and `resolved.groups.ventures` **keyed by page ID** (converted from the current name-keyed `resolved.businesses`), plus empty `tombstones`/`ignored`.

- [ ] **Step 1: Rewrite the file** by hand from the current map: move each `resolved.businesses[name]` to `resolved.groups.ventures[page_id] = {label: name, role: "tasks", tasks_db, cached_at}`; lift the old `business_tasks` schema into `child_schema_defaults.tasks`; put `university_tasks`/`schedule`/`modules` schemas under `role_schemas` keyed by their anchor DB IDs with `role` set; build the `areas` block. Keep the four real business entries currently present (drop the `ZZ Test Bakery` dummy + its `ignored` list from the uncommitted edit).

- [ ] **Step 2: Validate against the loader and a real run**

Run (from `lifeos-mcp/`, with `NOTION_TOKEN` set in env):
```bash
LIFEOS_MAP_PATH=../context/lifeos.map.json python -c "from lifeos_mcp.config import load_map; m=load_map('../context/lifeos.map.json'); assert m['areas'] and m['resolved']['groups']['ventures']; print('map OK')"
```
Expected: `map OK`.

- [ ] **Step 3: Commit**

```bash
git add context/lifeos.map.json
git commit -m "refactor(lifeos): migrate map to areas + ID-keyed resolved cache"
```

---

### Task 18: Register the server in the bot + project MCP config

**Files:**
- Modify: `telegram-bot/agent_runner.py:68-113` (`build_options`)
- Create/Modify: `.mcp.json` (project root)

**Interfaces:**
- Consumes: `lifeos-mcp` package + `server.main()`.
- Produces: the agent seeing five `mcp__lifeos__*` tools in both the bot and Claude Code.

- [ ] **Step 1: Add the lifeos stdio server in `build_options`**

In `mcp_servers` (after the google-calendar block), add:
```python
    # lifeos — our own deterministic tools (resolution + structured payloads).
    mcp_servers["lifeos"] = {
        "type": "stdio",
        "command": sys.executable,
        "args": ["-m", "lifeos_mcp.server"],
        "env": {
            "NOTION_TOKEN": NOTION_TOKEN,
            "GOOGLE_OAUTH_CREDENTIALS": GOOGLE_OAUTH_CREDENTIALS,
            "GOOGLE_CALENDAR_MCP_TOKEN_PATH": GOOGLE_CALENDAR_MCP_TOKEN_PATH,
            "LIFEOS_MAP_PATH": str(Path(PROJECT_DIR) / "context" / "lifeos.map.json"),
            "PYTHONPATH": str(Path(PROJECT_DIR) / "lifeos-mcp"),
        },
    }
```
And add `"mcp__lifeos"` to `allowed_tools`.

- [ ] **Step 2: Add `.mcp.json` for interactive Claude Code**

Create/extend project-root `.mcp.json`:
```json
{
  "mcpServers": {
    "lifeos": {
      "type": "stdio",
      "command": "python",
      "args": ["-m", "lifeos_mcp.server"],
      "env": { "PYTHONPATH": "lifeos-mcp" }
    }
  }
}
```

- [ ] **Step 3: Smoke-test the server starts over stdio**

Run (from repo root, `NOTION_TOKEN` set): `PYTHONPATH=lifeos-mcp python -m lifeos_mcp.server` then send Ctrl-C after it idles waiting for stdio (no crash on startup = pass). Alternatively run the unit suite again.
Expected: process starts and blocks on stdio without error.

- [ ] **Step 4: Commit**

```bash
git add telegram-bot/agent_runner.py .mcp.json
git commit -m "feat(lifeos): register lifeos MCP server in bot + project config"
```

---

### Task 19: Thin the skills + retire resolver.md

**Files:**
- Modify: `.claude/commands/today.md`, `.claude/commands/week.md`, `.claude/commands/add.md`
- Modify: `context/resolver.md` (replace with a pointer) ; Modify: `.claude/commands/refresh-notion.md`

**Interfaces:**
- Produces skills that call the lifeos tools and format the result; `/refresh-notion` emits the new `areas` schema.

- [ ] **Step 1: Rewrite `today.md`** to: "Call the `get_today` tool. If it returns `{error: reconnect_notion}`, tell the user to reconnect Notion. Otherwise render one block per `area` using its `label`/`emoji`, list `tasks` (mark `overdue`), `exams`, `shift`; then `events`. Keep the existing emoji headers as fallbacks." No IDs, no `resolver.md` reference, no column names.

- [ ] **Step 2: Rewrite `week.md`** to call `get_week` and render `days[]` grouped by date with the `summary`.

- [ ] **Step 3: Rewrite `add.md`** to call `add_record` (role + fields + optional area) for Notion rows and `create_event` for calendar; keep the routing table mapping user phrasing → role; keep the "records only, never create structures" scope line.

- [ ] **Step 4: Replace `context/resolver.md`** body with a short pointer: "Runtime resolution now lives in `lifeos-mcp/lifeos_mcp/resolver_*.py`, consumed by the lifeos MCP tools. This file is retained only as a pointer." 

- [ ] **Step 5: Update `refresh-notion.md`** so the map it writes uses `areas` + `role_schemas` + `child_schema_defaults` + ID-keyed `resolved.groups` (matching Task 17), and detects `done_when` vs `status_values.done`.

- [ ] **Step 6: No-ID gate over skills**

Run:
```bash
rg -nE "[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}|[0-9a-f]{32}|collection://" .claude/commands/today.md .claude/commands/week.md .claude/commands/add.md .claude/commands/refresh-notion.md; echo "exit:$?"
```
Expected: no output, non-zero exit.

- [ ] **Step 7: Commit**

```bash
git add .claude/commands/today.md .claude/commands/week.md .claude/commands/add.md .claude/commands/refresh-notion.md context/resolver.md
git commit -m "refactor(lifeos): thin skills onto lifeos tools; retire resolver.md"
```

---

### Task 20: Live validation (manual, against real Notion + Calendar)

**Files:** none (record results in `verify/lifeos-mcp.md`)

- [ ] **Step 1: Parity** — run `/today` and `/week` (bot or Claude Code) and confirm the same tasks/shifts/deadlines/events as the pre-change skills. Record output.
- [ ] **Step 2: Routing** — `/add` a task, an exam (with exam_date), a shift, and a calendar event; confirm each lands in the right destination via the tools.
- [ ] **Step 3: New-venture auto-pickup** — add a dummy business page + tasks DB in Notion; run `/today`; confirm it appears with no map/skill edit and gets written to `resolved.groups.ventures` keyed by ID.
- [ ] **Step 4: Renamed column** — rename a task DB's due column; run `/refresh-notion`; confirm `/today` still filters via the updated `role_schemas`.
- [ ] **Step 5: Archived/deleted** — archive the dummy venture; run `/today`; confirm it is tombstoned (not a mass prune) and the rest of the briefing is intact.
- [ ] **Step 6: Safety** — temporarily point `LIFEOS_MAP_PATH` at an empty/garbage map (or revoke token in a scratch run); confirm tools return `reconnect_notion` rather than an empty briefing.
- [ ] **Step 7: Clean up** the dummy venture; record all results in `verify/lifeos-mcp.md`; commit the verify log.

```bash
git add verify/lifeos-mcp.md
git commit -m "test(lifeos): live validation log for lifeos MCP server v1"
```

---

## Self-Review

**Spec coverage:**
- Approach A standalone FastMCP stdio server, direct APIs → Tasks 1, 8, 9, 14, 18. ✅
- Tools get_today/get_week/query_records/add_record/create_event, structured output → Tasks 10–14. ✅
- Generic roles (tasks/schedule/catalog) + map-declared areas → map shape, Tasks 3, 5, 6. ✅
- Portability contract (map-swap, absent role = empty) → Task 15 + get_today area loop. ✅
- Shape refinements A (child_sources list), C (done_when), D (absent prop) → Tasks 5, 6 + map shape. ✅
- Nested groups deferred → not implemented; one group level only. ✅
- Stale rules i–v (ID-keyed, error classes, blast-radius, tombstones, rename-safe) → Task 7. ✅
- Error handling (wrong workspace, partial failure, ambiguity surface) → Tasks 10/11 warnings, Task 14 reconnect_notion. (Ambiguity `needs_disambiguation` is surfaced via `add_record` returning `{created: False, error}` and resolver returning `None`; full ask-then-remember flow is an agent/skill concern documented in Task 19.) ✅
- Calendar owned by server → Task 9, 13. ✅
- Map migration + resolver.md retire + skills thinned + /refresh-notion updated → Tasks 17, 19. ✅
- Registration in bot + .mcp.json → Task 18. ✅
- Testing (unit, tool, map-swap, live, no-ID gate) → Tasks 5–16, 20. ✅
- Out of scope (vault, update/mark_done, structures, multi-user backend) → not planned here. ✅

**Placeholder scan:** every code step shows full code; every verify step has a command + expected output; the only intentional `<id>` tokens are in the JSON *shape reference* (not executable). The Task 14 `for ... pass` stub is explicitly removed in Step 3b. No TBD/TODO. ✅

**Type/name consistency:** `resolve_sources`/`resolve_named`/`ResolvedSource`, `schema_for`/`prop`/`is_done`, `extract_props`/`build_props`, `get_today`/`get_week`/`query_records`/`add_record`/`create_event`, `_to_date`, `week_bounds`, payload `to_dict()` are used identically across Tasks 3–15. Tool registry names match `allowed_tools` (`mcp__lifeos`). ✅
