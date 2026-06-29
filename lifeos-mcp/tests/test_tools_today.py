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
    m.setdefault("resolved", {}).setdefault("reconciled", {})["ventures"] = "2026-06-27"  # skip daily reconcile
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
    m.setdefault("resolved", {}).setdefault("reconciled", {})["ventures"] = "2026-06-27"  # skip daily reconcile
    notion = FakeNotionClient(rows={"uni-tasks": [_row("Essay","Open","2026-06-27")]},
                              fail_with={"laundro-db": TransientError})
    cal = FakeCalendarClient()
    payload = get_today(m, notion, cal, date(2026, 6, 27))
    assert any("laundro-db" in w for w in payload.warnings)
    assert any(t.title == "Essay" for a in payload.areas for t in a.tasks)

def test_today_calendar_window_uses_berlin_offset():
    import copy
    from datetime import date
    m = copy.deepcopy(FIXTURE_MAP)
    cal = FakeCalendarClient()
    get_today(m, FakeNotionClient(), cal, date(2026, 6, 27))  # default tz Europe/Berlin (CEST, +02:00 in summer)
    tmin, tmax = cal.list_calls[-1]
    assert tmin.startswith("2026-06-27T00:00:00")
    assert tmin.endswith("+02:00")   # Berlin summer offset, not UTC 'Z'

def test_today_calendar_failure_warns_and_empty():
    import copy
    from datetime import date
    m = copy.deepcopy(FIXTURE_MAP)
    class BoomCal:
        def list_events(self, a, b):
            raise RuntimeError("cal down")
    payload = get_today(m, FakeNotionClient(), BoomCal(), date(2026, 6, 27))
    assert any("calendar failed" in w for w in payload.warnings)
    assert payload.events == []

def test_today_tags_tasks_with_source_label():
    m = copy.deepcopy(FIXTURE_MAP)
    m.setdefault("resolved", {}).setdefault("reconciled", {})["ventures"] = "2026-06-27"  # skip daily reconcile
    notion = FakeNotionClient(rows={
        "uni-tasks": [_row("Essay", "Open", "2026-06-27")],
        "laundro-db": [_row("Call landlord", "Open", "2026-06-26")]})
    payload = get_today(m, notion, FakeCalendarClient(), date(2026, 6, 27))
    by_title = {t.title: t for a in payload.areas for t in a.tasks}
    assert by_title["Call landlord"].source_label == "Laundromat Hannover"
    assert by_title["Essay"].source_label is None
    assert by_title["Call landlord"].to_dict()["source_label"] == "Laundromat Hannover"

def test_today_group_discovery_failure_warns_not_aborts():
    from lifeos_mcp.errors import TransientError
    m = copy.deepcopy(FIXTURE_MAP)
    m["resolved"]["groups"]["ventures"] = {}            # force cache miss
    notion = FakeNotionClient(
        rows={"uni-tasks": [_row("Essay", "Open", "2026-06-27")]},
        fail_with={"biz-root": TransientError})
    payload = get_today(m, notion, FakeCalendarClient(), date(2026, 6, 27))
    assert any("ventures" in w for w in payload.warnings)
    assert any(t.title == "Essay" for a in payload.areas for t in a.tasks)

def test_today_b_reflects_direct_notion_rename():
    m = copy.deepcopy(FIXTURE_MAP)
    notion = FakeNotionClient(
        children={"biz-root": [{"id": "laundro-page", "title": "Laundromat HQ"}]},
        child_db={"laundro-page": "laundro-db"},
        rows={"laundro-db": [_row("Soap", "Open", "2026-06-27")]})
    p = get_today(m, notion, FakeCalendarClient(), date(2026, 6, 27))
    assert any(t.source_label == "Laundromat HQ" for a in p.areas for t in a.tasks)

def test_today_b_daily_gate_holds():
    m = copy.deepcopy(FIXTURE_MAP)
    notion = FakeNotionClient(
        children={"biz-root": [{"id": "laundro-page", "title": "First"}]},
        child_db={"laundro-page": "laundro-db"},
        rows={"laundro-db": [_row("Soap", "Open", "2026-06-27")]})
    get_today(m, notion, FakeCalendarClient(), date(2026, 6, 27))        # stamps; label -> First
    notion.children = {"biz-root": [{"id": "laundro-page", "title": "Second"}]}  # renamed again, same day
    p = get_today(m, notion, FakeCalendarClient(), date(2026, 6, 27))
    labels = {t.source_label for a in p.areas for t in a.tasks}
    assert "First" in labels and "Second" not in labels                 # gate skipped re-reconcile

def test_today_b_transient_reconcile_warns_keeps_cache():
    from lifeos_mcp.errors import TransientError
    m = copy.deepcopy(FIXTURE_MAP)
    notion = FakeNotionClient(fail_with={"biz-root": TransientError},
        rows={"uni-tasks": [_row("Essay", "Open", "2026-06-27")],
              "laundro-db": [_row("Soap", "Open", "2026-06-27")]})
    p = get_today(m, notion, FakeCalendarClient(), date(2026, 6, 27))
    assert any("reconcile" in w for w in p.warnings)
    assert "Soap" in {t.title for a in p.areas for t in a.tasks}         # stale cache still used

def test_today_b_blast_radius_raises_workspace_unavailable():
    import pytest
    from lifeos_mcp.errors import NotionAuthError, WorkspaceUnavailable
    m = copy.deepcopy(FIXTURE_MAP)
    m["resolved"]["groups"]["ventures"]["second-page"] = {
        "label": "Two", "role": "tasks", "tasks_db": "two-db", "cached_at": "2026-06-26"}
    notion = FakeNotionClient(children={"biz-root": []},
        fail_with={"laundro-page": NotionAuthError, "second-page": NotionAuthError})
    with pytest.raises(WorkspaceUnavailable):
        get_today(m, notion, FakeCalendarClient(), date(2026, 6, 27))

def test_today_d_self_heals_deleted_venture_after_daily_reconcile():
    from lifeos_mcp.errors import NotionNotFound
    m = copy.deepcopy(FIXTURE_MAP)
    # B already ran today -> the daily gate will skip; only D can react
    m.setdefault("resolved", {}).setdefault("reconciled", {})["ventures"] = "2026-06-27"
    notion = FakeNotionClient(
        children={"biz-root": []},                       # laundro-page gone from Notion
        rows={"uni-tasks": [_row("Essay", "Open", "2026-06-27")]},
        fail_with={"laundro-db": NotionNotFound,          # query 404 -> triggers D
                   "laundro-page": NotionNotFound})        # retrieve 404 -> reconcile classifies deleted
    p = get_today(m, notion, FakeCalendarClient(), date(2026, 6, 27))
    assert any(t.title == "Essay" for a in p.areas for t in a.tasks)     # briefing survives
    assert "laundro-page" not in m["resolved"]["groups"]["ventures"]      # D tombstoned it
    assert "laundro-page" in m["resolved"]["tombstones"]

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
