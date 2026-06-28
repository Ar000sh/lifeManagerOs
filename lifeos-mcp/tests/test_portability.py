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

def test_alt_map_tags_discovered_venture_source_label():
    from tests.fixtures.maps import ALT_MAP
    m = copy.deepcopy(ALT_MAP)
    row = {"id": "c1", "url": "u", "properties": {
        "Name": {"type": "title", "title": [{"plain_text": "Call client"}]},
        "Due": {"type": "date", "date": {"start": "2026-06-27"}},
        "Status": {"type": "select", "select": {"name": "Open"}}}}
    notion = FakeNotionClient(
        children={"client-root": [{"id": "acme-page", "title": "Acme GmbH"}]},
        child_db={"acme-page": "acme-db"},
        rows={"acme-db": [row]})
    payload = get_today(m, notion, FakeCalendarClient(), date(2026, 6, 27))
    by_title = {t.title: t for a in payload.areas for t in a.tasks}
    assert by_title["Call client"].source_label == "Acme GmbH"
