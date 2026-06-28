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

def test_week_task_items_carry_source_label():
    m = copy.deepcopy(FIXTURE_MAP)
    m.setdefault("resolved", {}).setdefault("reconciled", {})["ventures"] = "2026-06-27"  # skip daily reconcile
    row = {"id": "t1", "url": "u", "properties": {
        "Name": {"type": "title", "title": [{"plain_text": "Soap order"}]},
        "Status": {"type": "select", "select": {"name": "Open"}},
        "Due Date": {"type": "date", "date": {"start": "2026-06-25"}}}}
    notion = FakeNotionClient(rows={"laundro-db": [row]})
    payload = get_week(m, notion, FakeCalendarClient(), date(2026, 6, 27))
    items = [it for d in payload.days for it in d["tasks"]]
    assert any(it["title"] == "Soap order" and it["source_label"] == "Laundromat Hannover"
               for it in items)
