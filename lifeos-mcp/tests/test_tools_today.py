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
