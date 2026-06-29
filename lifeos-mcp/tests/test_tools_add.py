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
    # No area + multiple task sources (uni + laundro) is now ambiguous, not a silent pick.
    m = copy.deepcopy(FIXTURE_MAP)
    notion = FakeNotionClient()
    res = add_record(m, notion, "tasks", {"title": "Read ch.3"})
    assert res["created"] is False
    assert res["error"] == "ambiguous_destination"
    assert "University" in res["candidates"]
    assert "Laundromat Hannover" in res["candidates"]
    assert notion.created == []   # nothing was written

def test_add_ambiguous_business_returns_candidates():
    m = copy.deepcopy(FIXTURE_MAP)
    # add a second venture so "Business" maps to >1 candidate
    m["resolved"]["groups"]["ventures"]["van-page"] = {
        "label": "Van Company", "role": "tasks", "tasks_db": "van-db",
        "cached_at": "2026-06-26"}
    notion = FakeNotionClient()
    res = add_record(m, notion, "tasks", {"title": "Plan"}, area="Business")
    assert res["created"] is False
    assert res["error"] == "ambiguous_destination"
    assert res["candidates"] == ["Laundromat Hannover", "Van Company"]
    assert notion.created == []

def test_add_unknown_area_returns_not_found():
    m = copy.deepcopy(FIXTURE_MAP)
    notion = FakeNotionClient()
    res = add_record(m, notion, "tasks", {"title": "x"}, area="Bakery")
    assert res["created"] is False
    assert res["error"] == "destination_not_found"
    assert res["candidates"] == ["Laundromat Hannover", "University"]
    assert notion.created == []

def test_create_event_defaults_one_hour():
    cal = FakeCalendarClient()
    res = create_event(cal, "Call", "2026-06-27T10:00:00+02:00")
    assert res["created"] is True
    title, start, end, notes = cal.created[-1]
    assert end == "2026-06-27T11:00:00+02:00"

def test_add_task_to_area_by_label_resolves_anchor():
    m = copy.deepcopy(FIXTURE_MAP)
    notion = FakeNotionClient()
    add_record(m, notion, "tasks", {"title": "Read ch.3", "due_date": "2026-07-01"}, area="University")
    assert notion.created[-1][0] == "uni-tasks"   # area-label match -> anchored uni source

def test_add_to_named_business_reports_venture_destination():
    m = copy.deepcopy(FIXTURE_MAP)
    notion = FakeNotionClient()
    res = add_record(m, notion, "tasks", {"title": "Order soap", "due_date": "2026-07-01"}, area="Laundromat")
    assert res["destination"] == "Laundromat Hannover"

def test_add_to_anchored_area_reports_area_destination():
    m = copy.deepcopy(FIXTURE_MAP)
    notion = FakeNotionClient()
    res = add_record(m, notion, "tasks", {"title": "Read ch.3", "due_date": "2026-07-01"}, area="University")
    assert res["destination"] == "University"

def test_add_refuses_missing_required_due_date():
    m = copy.deepcopy(FIXTURE_MAP)
    notion = FakeNotionClient()
    res = add_record(m, notion, "tasks", {"title": "No date"}, area="University")
    assert res["created"] is False
    assert res["error"] == "missing_required"
    assert res["fields"] == ["due_date"]
    assert notion.created == []
