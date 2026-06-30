"""Ad-hoc edge-case review of the dynamic-schema flow.
Run: python3 -m pytest tests/test_edgecases_review.py -q
Each test probes a scenario the unit suite does not, to confirm correct data,
error handling, and warnings end-to-end.
"""
import copy
from datetime import date
import pytest

from lifeos_mcp.tools.get_today import get_today, _task_rows
from lifeos_mcp.tools.get_week import get_week
from lifeos_mcp.tools.query_records import query_records
from lifeos_mcp.tools.add_record import add_record
from lifeos_mcp.notion_client import extract_props, build_props
from lifeos_mcp.resolver_schema import is_complete, required_core, key_date_fields
from tests.fixtures.maps import FIXTURE_MAP, ALT_MAP
from tests.fakes import FakeNotionClient, FakeCalendarClient

TODAY = date(2026, 6, 27)

def _skip_reconcile(m):
    m.setdefault("resolved", {}).setdefault("reconciled", {})["ventures"] = TODAY.isoformat()
    return m

def _uni_row(title="ML", status="Open", due="2026-06-27", exam=None, module=None, prio=None):
    props = {"Name": {"type": "title", "title": [{"plain_text": title}]},
             "Status": {"type": "select", "select": {"name": status}}}
    if due is not None:
        props["Due Date"] = {"type": "date", "date": {"start": due}}
    if exam is not None:
        props["Exam Date"] = {"type": "date", "date": {"start": exam}}
    if module is not None:
        props["Module"] = {"type": "relation", "relation": [{"id": m} for m in module]}
    if prio is not None:
        props["Priority"] = {"type": "select", "select": {"name": prio}}
    return {"id": title, "url": f"http://n/{title}", "properties": props}


# ── 1. Future-due task: excluded from today's tasks, but its key date IS surfaced ──
def test_future_task_hidden_but_keydate_surfaced():
    m = _skip_reconcile(copy.deepcopy(FIXTURE_MAP))
    notion = FakeNotionClient(rows={"uni-tasks": [
        _uni_row("FutureExam", "Open", due="2026-08-01", exam="2026-07-10")]})
    p = get_today(m, notion, FakeCalendarClient(), TODAY)
    titles = {t.title for a in p.areas for t in a.tasks}
    kds = [kd for a in p.areas for kd in a.key_dates]
    assert "FutureExam" not in titles            # future due -> not in today's list
    assert any(kd["label"] == "Exam Date" for kd in kds)   # but exam surfaced


# ── 2. A long-past key date on an open task is NOT surfaced (noise suppressed) ──
def test_past_keydate_not_surfaced_today():
    m = _skip_reconcile(copy.deepcopy(FIXTURE_MAP))
    notion = FakeNotionClient(rows={"uni-tasks": [
        _uni_row("OldExam", "Open", due="2026-06-27", exam="2026-01-01")]})
    p = get_today(m, notion, FakeCalendarClient(), TODAY)
    kds = [kd for a in p.areas for kd in a.key_dates]
    assert not any(kd["date"] == "2026-01-01" for kd in kds)   # past -> hidden
    rec = [t for a in p.areas for t in a.tasks][0]
    assert rec.fields["exam_date"] == "2026-01-01"   # still carried inline on the record
    assert rec.key_dates == []                        # but not promoted to a key date


# ── 3. Relation field round-trips on read into Record.fields ──
def test_relation_field_carried_on_read():
    m = _skip_reconcile(copy.deepcopy(FIXTURE_MAP))
    notion = FakeNotionClient(rows={"uni-tasks": [
        _uni_row("Linked", "Open", due="2026-06-27", module=["mod-1", "mod-2"])]})
    p = get_today(m, notion, FakeCalendarClient(), TODAY)
    rec = [t for a in p.areas for t in a.tasks][0]
    assert rec.fields["module"] == ["mod-1", "mod-2"]
    assert rec.to_dict()["fields"]["module"] == ["mod-1", "mod-2"]


# ── 4. Highlighted date appears in BOTH key_dates and fields (per impl) ──
def test_highlighted_date_in_fields_and_keydates():
    m = _skip_reconcile(copy.deepcopy(FIXTURE_MAP))
    notion = FakeNotionClient(rows={"uni-tasks": [
        _uni_row("Both", "Open", due="2026-06-27", exam="2026-07-10")]})
    p = get_today(m, notion, FakeCalendarClient(), TODAY)
    rec = [t for a in p.areas for t in a.tasks][0]
    assert rec.fields.get("exam_date") == "2026-07-10"        # inline copy
    assert any(k.label == "Exam Date" for k in rec.key_dates)  # and highlighted


# ── 5. Done task: its key date is NOT surfaced (filtered before keydate walk) ──
def test_done_task_keydate_suppressed():
    m = _skip_reconcile(copy.deepcopy(FIXTURE_MAP))
    notion = FakeNotionClient(rows={"uni-tasks": [
        _uni_row("DoneExam", "Done", due="2026-06-27", exam="2026-07-10")]})
    p = get_today(m, notion, FakeCalendarClient(), TODAY)
    kds = [kd for a in p.areas for kd in a.key_dates]
    assert kds == []


# ── 6. Missing title is flagged but the row is still emitted ──
def test_missing_title_warns_and_emits():
    m = _skip_reconcile(copy.deepcopy(FIXTURE_MAP))
    row = {"id": "noname", "url": "u", "properties": {
        "Status": {"type": "select", "select": {"name": "Open"}},
        "Due Date": {"type": "date", "date": {"start": "2026-06-27"}}}}
    notion = FakeNotionClient(rows={"uni-tasks": [row]})
    p = get_today(m, notion, FakeCalendarClient(), TODAY)
    assert any("missing required title" in w for w in p.warnings)
    assert any(t.id == "noname" for a in p.areas for t in a.tasks)  # still emitted


# ── 7. Overdue flag set for past-due open task ──
def test_overdue_flag():
    m = _skip_reconcile(copy.deepcopy(FIXTURE_MAP))
    notion = FakeNotionClient(rows={"uni-tasks": [
        _uni_row("Late", "Open", due="2026-06-20")]})
    p = get_today(m, notion, FakeCalendarClient(), TODAY)
    rec = [t for a in p.areas for t in a.tasks][0]
    assert rec.overdue is True


# ── 8. add_record into schedule role requires title + date ──
def test_add_schedule_requires_date():
    m = copy.deepcopy(FIXTURE_MAP)
    notion = FakeNotionClient()
    res = add_record(m, notion, "schedule", {"title": "Shift"}, area="Work")
    assert res["created"] is False and res["error"] == "missing_required"
    assert res["fields"] == ["date"]
    ok = add_record(m, notion, "schedule",
                    {"title": "Shift", "date": "2026-06-27", "start": "09:00", "end": "17:00"},
                    area="Work")
    assert ok["created"] is True
    db, props = notion.created[-1]
    assert db == "work-db"
    assert props["Start Time"]["rich_text"][0]["text"]["content"] == "09:00"


# ── 9. add_record writes a relation field ──
def test_add_writes_relation():
    m = copy.deepcopy(FIXTURE_MAP)
    notion = FakeNotionClient()
    res = add_record(m, notion, "tasks",
                     {"title": "Linked", "due_date": "2026-07-01", "module": ["mod-9"]},
                     area="University")
    assert res["created"] is True
    db, props = notion.created[-1]
    assert props["Module"]["relation"] == [{"id": "mod-9"}]


# ── 10. query catalog role: reachable (area["catalog"] now resolved) ──
def test_query_catalog_role_reachable():
    # resolve_sources now scans area["catalog"] in addition to sources/group,
    # so the modules catalog is queryable through query_records.
    m = copy.deepcopy(FIXTURE_MAP)
    notion = FakeNotionClient(rows={"mod-db": [
        {"id": "m1", "url": "u", "properties": {
            "Name": {"type": "title", "title": [{"plain_text": "Algorithms"}]}}}]})
    res = query_records(m, notion, "catalog")
    assert [r["title"] for r in res] == ["Algorithms"]


# ── 11. query not_done via checkbox predicate (ALT map) ──
def test_query_not_done_checkbox():
    m = copy.deepcopy(ALT_MAP)
    notion = FakeNotionClient(rows={"todo-db": [
        {"id": "a", "url": "u", "properties": {
            "Titel": {"type": "title", "title": [{"plain_text": "Open one"}]},
            "Fällig": {"type": "date", "date": {"start": "2026-06-27"}},
            "Erledigt": {"type": "checkbox", "checkbox": False}}},
        {"id": "b", "url": "u", "properties": {
            "Titel": {"type": "title", "title": [{"plain_text": "Done one"}]},
            "Fällig": {"type": "date", "date": {"start": "2026-06-20"}},
            "Erledigt": {"type": "checkbox", "checkbox": True}}}]})
    res = query_records(m, notion, "tasks", {"not_done": True})
    assert [r["title"] for r in res] == ["Open one"]


# ── 12. extract_props drops an unhandled Notion type (multi_select) ──
def test_extract_props_drops_unhandled_type():
    page = {"properties": {
        "Tags": {"type": "multi_select", "multi_select": [{"name": "x"}]},
        "Name": {"type": "title", "title": [{"plain_text": "T"}]}}}
    props = extract_props(page)
    assert "Tags" not in props          # FINDING: multi_select/people/etc. silently dropped
    assert props["Name"] == "T"


# ── 13. is_complete when checkbox property is absent on the row ──
def test_is_complete_missing_checkbox_is_not_done():
    sch = ALT_MAP["role_schemas"]["todo_db"]
    assert is_complete(sch, {}) is False   # absent Erledigt -> treated not done


# ── 14. get_week isolates a malformed calendar event (others still bucket) ──
def test_week_malformed_calendar_event_isolated():
    m = _skip_reconcile(copy.deepcopy(FIXTURE_MAP))
    cal = FakeCalendarClient(events=[
        {"id": "bad", "title": "Bad", "start": "not-a-date", "end": "y"},
        {"id": "good", "title": "Standup", "start": "2026-06-25", "end": "2026-06-25"}])
    p = get_week(m, FakeNotionClient(), cal, TODAY)
    assert any("calendar event" in w for w in p.warnings)   # bad one warned, not the batch
    all_events = [e for d in p.days for e in d["events"]]
    assert any(e["title"] == "Standup" for e in all_events)  # good one still survives


# ── 15. get_today does NOT date-parse calendar events (passes opaque start through) ──
def test_today_calendar_event_start_passthrough():
    m = _skip_reconcile(copy.deepcopy(FIXTURE_MAP))
    cal = FakeCalendarClient(events=[{"id": "e", "title": "Standup", "start": "x", "end": "y"}])
    p = get_today(m, FakeNotionClient(), cal, TODAY)
    assert p.events[0].start == "x"   # today tolerates non-ISO start; week does not


# ── 16. add_record rejects empty/blank required values (presence + non-blank) ──
def test_add_empty_string_required_rejected():
    m = copy.deepcopy(FIXTURE_MAP)
    notion = FakeNotionClient()
    res = add_record(m, notion, "tasks",
                     {"title": "", "due_date": ""}, area="University")
    # blank strings are treated as missing, not silently written as {"start": ""}
    assert res["created"] is False
    assert res["error"] == "missing_required"
    assert res["fields"] == ["title", "due_date"]
    assert notion.created == []


# ── 17. Two highlighted date fields both surface as separate key dates ──
def test_two_keydate_fields():
    m = _skip_reconcile(copy.deepcopy(FIXTURE_MAP))
    m["role_schemas"]["university_tasks_db"]["fields"]["registration"] = {
        "col": "Registration", "type": "date", "highlight": True}
    sch = m["role_schemas"]["university_tasks_db"]
    assert {k for k, _ in key_date_fields(sch)} == {"exam_date", "registration"}
    row = _uni_row("Multi", "Open", due="2026-06-27", exam="2026-07-10")
    row["properties"]["Registration"] = {"type": "date", "date": {"start": "2026-07-05"}}
    notion = FakeNotionClient(rows={"uni-tasks": [row]})
    p = get_today(m, notion, FakeCalendarClient(), TODAY)
    labels = {kd["label"] for a in p.areas for kd in a.key_dates}
    assert labels == {"Exam Date", "Registration"}


# ── 18. priority default only applied when schema declares a priority column ──
def test_priority_default_applied_for_uni_not_for_alt():
    m = copy.deepcopy(FIXTURE_MAP)
    notion = FakeNotionClient()
    add_record(m, notion, "tasks", {"title": "P", "due_date": "2026-07-01"}, area="University")
    _, props = notion.created[-1]
    assert props["Priority"]["select"]["name"] == "Medium"

    m2 = copy.deepcopy(ALT_MAP)
    notion2 = FakeNotionClient()
    add_record(m2, notion2, "tasks", {"title": "P", "due_date": "2026-07-01"}, area="Persönlich")
    _, props2 = notion2.created[-1]
    assert "Priority" not in props2   # ALT todo has no priority col -> no default


# ── 19. get_week: out-of-range task with week_predicate lands on Monday ──
def test_week_predicate_buckets_to_monday():
    m = _skip_reconcile(copy.deepcopy(FIXTURE_MAP))
    # due far in the future, but Status == "This Week"
    row = _uni_row("Floating", "This Week", due="2026-09-01")
    notion = FakeNotionClient(rows={"uni-tasks": [row]})
    p = get_week(m, notion, FakeCalendarClient(), TODAY)
    monday = p.start.isoformat()
    day = next(d for d in p.days if d["date"] == monday)
    assert any(it["title"] == "Floating" for it in day["tasks"])


# ── 20. get_week: a task can appear as both a task (due in range) and a key date ──
def test_week_task_and_keydate_both_appear():
    m = _skip_reconcile(copy.deepcopy(FIXTURE_MAP))
    row = _uni_row("DualSection", "Open", due="2026-06-25", exam="2026-06-24")
    notion = FakeNotionClient(rows={"uni-tasks": [row]})
    p = get_week(m, notion, FakeCalendarClient(), TODAY)
    all_tasks = [it for d in p.days for it in d["tasks"]]
    all_kds = [k for d in p.days for k in d["key_dates"]]
    assert any(it["title"] == "DualSection" for it in all_tasks)
    assert any(k["title"] == "DualSection" and k["label"] == "Exam Date" for k in all_kds)
    assert p.summary["tasks"] >= 1 and p.summary["key_dates"] >= 1


# ── 21. MCP server boundary: WorkspaceUnavailable -> reconnect, map not corrupted ──
def test_server_today_reconnect_on_workspace_unavailable(tmp_path):
    import json
    from lifeos_mcp.config import Settings
    from lifeos_mcp.server import build_app
    from lifeos_mcp.errors import NotionAuthError

    m = copy.deepcopy(FIXTURE_MAP)
    # two ventures both auth-failing during reconcile -> blast-radius -> WorkspaceUnavailable
    m["resolved"]["groups"]["ventures"]["second-page"] = {
        "label": "Two", "role": "tasks", "tasks_db": "two-db", "cached_at": "2026-06-26"}
    map_path = tmp_path / "map.json"
    map_path.write_text(json.dumps(m))

    notion = FakeNotionClient(children={"biz-root": []},
        fail_with={"laundro-page": NotionAuthError, "second-page": NotionAuthError})
    settings = Settings(notion_token="t", google_credentials="{}",
                        google_token_path="/x", map_path=str(map_path), tz="Europe/Berlin")
    app = build_app(settings, notion=notion, calendar=FakeCalendarClient())

    fn = app._tool_manager.get_tool("get_today").fn
    result = fn()
    assert result == {"error": "reconnect_notion"}
    # map file on disk must be unchanged (no half-reconcile persisted)
    assert json.loads(map_path.read_text()) == m


def _two_keydate_map():
    m = _skip_reconcile(copy.deepcopy(FIXTURE_MAP))
    m["role_schemas"]["university_tasks_db"]["fields"]["registration"] = {
        "col": "Registration", "type": "date", "highlight": True}
    return m

def _two_keydate_row(title, due, exam, registration):
    row = _uni_row(title, "Open", due=due, exam=exam)
    row["properties"]["Registration"] = {"type": "date", "date": {"start": registration}}
    return row


# ── 22. today: one key date finished + one upcoming -> ONLY the upcoming surfaces ──
def test_today_multi_keydate_mixed_validity_surfaces_only_upcoming():
    m = _two_keydate_map()
    # exam already finished (past), registration still upcoming
    notion = FakeNotionClient(rows={"uni-tasks": [
        _two_keydate_row("Course", due="2026-06-27", exam="2026-01-01", registration="2026-07-10")]})
    p = get_today(m, notion, FakeCalendarClient(), TODAY)
    kds = [kd for a in p.areas for kd in a.key_dates]
    assert {kd["label"] for kd in kds} == {"Registration"}     # finished one hidden
    rec = [t for a in p.areas for t in a.tasks][0]
    assert {k.label for k in rec.key_dates} == {"Registration"}
    assert rec.fields["exam_date"] == "2026-01-01"             # finished date still inline


# ── 23. today: both key dates upcoming -> two DISTINCT entries (not a duplicate) ──
def test_today_multi_keydate_both_valid_two_distinct_entries():
    m = _two_keydate_map()
    notion = FakeNotionClient(rows={"uni-tasks": [
        _two_keydate_row("Course", due="2026-06-27", exam="2026-07-10", registration="2026-07-05")]})
    p = get_today(m, notion, FakeCalendarClient(), TODAY)
    kds = [kd for a in p.areas for kd in a.key_dates]
    assert len(kds) == 2                                       # one per field, no dup
    assert {kd["label"] for kd in kds} == {"Exam Date", "Registration"}
    assert {kd["date"] for kd in kds} == {"2026-07-10", "2026-07-05"}


# ── 24. week: one key date out of range + one in range -> ONLY the in-range surfaces ──
def test_week_multi_keydate_only_in_range_surfaces():
    m = _two_keydate_map()
    notion = FakeNotionClient(rows={"uni-tasks": [
        _two_keydate_row("Course", due="2026-06-25", exam="2026-01-01", registration="2026-06-26")]})
    p = get_week(m, notion, FakeCalendarClient(), TODAY)
    kds = [k for d in p.days for k in d["key_dates"]]
    assert {k["label"] for k in kds} == {"Registration"}       # out-of-week one dropped
    assert p.summary["key_dates"] == 1


# ── 25. week: both key dates in range -> two DISTINCT entries ──
def test_week_multi_keydate_both_in_range_two_entries():
    m = _two_keydate_map()
    notion = FakeNotionClient(rows={"uni-tasks": [
        _two_keydate_row("Course", due="2026-06-25", exam="2026-06-24", registration="2026-06-26")]})
    p = get_week(m, notion, FakeCalendarClient(), TODAY)
    kds = [k for d in p.days for k in d["key_dates"]]
    assert len(kds) == 2
    assert {k["label"] for k in kds} == {"Exam Date", "Registration"}
    assert p.summary["key_dates"] == 2
