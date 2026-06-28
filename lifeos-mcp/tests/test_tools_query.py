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

def test_query_filter_by_venture_name_matches_source_label():
    m = copy.deepcopy(FIXTURE_MAP)
    notion = FakeNotionClient(rows={
        "uni-tasks": [_row("Essay", "Open", "2026-07-01")],
        "laundro-db": [_row("Soap", "Open", "2026-07-02")]})
    res = query_records(m, notion, "tasks", {"area": "Laundromat"})
    assert [r["title"] for r in res] == ["Soap"]
    assert res[0]["source_label"] == "Laundromat Hannover"

def test_query_filter_by_area_still_returns_all_ventures():
    m = copy.deepcopy(FIXTURE_MAP)
    notion = FakeNotionClient(rows={"laundro-db": [_row("Soap", "Open", "2026-07-02")]})
    res = query_records(m, notion, "tasks", {"area": "Business"})
    assert [r["title"] for r in res] == ["Soap"]
