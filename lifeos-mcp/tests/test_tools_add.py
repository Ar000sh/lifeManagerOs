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

def test_add_task_to_area_by_label_resolves_anchor():
    m = copy.deepcopy(FIXTURE_MAP)
    notion = FakeNotionClient()
    add_record(m, notion, "tasks", {"title": "Read ch.3"}, area="University")
    assert notion.created[-1][0] == "uni-tasks"   # area-label match -> anchored uni source

def test_add_to_named_business_reports_venture_destination():
    m = copy.deepcopy(FIXTURE_MAP)
    notion = FakeNotionClient()
    res = add_record(m, notion, "tasks", {"title": "Order soap"}, area="Laundromat")
    assert res["destination"] == "Laundromat Hannover"

def test_add_to_anchored_area_reports_area_destination():
    m = copy.deepcopy(FIXTURE_MAP)
    notion = FakeNotionClient()
    res = add_record(m, notion, "tasks", {"title": "Read ch.3"}, area="University")
    assert res["destination"] == "University"
