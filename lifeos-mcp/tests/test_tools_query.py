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
