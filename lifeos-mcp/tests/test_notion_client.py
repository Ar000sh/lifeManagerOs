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

def test_extract_props_reads_number_and_relation():
    page = {"properties": {
        "Estimate": {"type": "number", "number": 3.5},
        "Module": {"type": "relation", "relation": [{"id": "mod-1"}, {"id": "mod-2"}]}}}
    props = extract_props(page)
    assert props["Estimate"] == 3.5
    assert props["Module"] == ["mod-1", "mod-2"]

def test_retrieve_403_maps_to_auth():
    import pytest, httpx
    from lifeos_mcp.errors import NotionAuthError
    c = _client(lambda req: httpx.Response(403, json={}))
    with pytest.raises(NotionAuthError):
        c.retrieve("x")

def test_retrieve_429_maps_to_transient():
    import pytest, httpx
    from lifeos_mcp.errors import TransientError
    c = _client(lambda req: httpx.Response(429, json={}))
    with pytest.raises(TransientError):
        c.retrieve("x")

def test_retrieve_500_maps_to_transient():
    import pytest, httpx
    from lifeos_mcp.errors import TransientError
    c = _client(lambda req: httpx.Response(500, json={}))
    with pytest.raises(TransientError):
        c.retrieve("x")

def test_build_props_skips_none_and_maps_types():
    from lifeos_mcp.notion_client import build_props
    schema = {"title": "Name", "status": "Status", "due_date": "Due Date", "notes": "Notes"}
    out = build_props(schema, {"title": "Buy soap", "status": "Open",
                               "due_date": "2026-07-01", "notes": None,
                               "missing_role": "x"})
    assert out["Name"]["title"][0]["text"]["content"] == "Buy soap"
    assert out["Status"]["select"]["name"] == "Open"
    assert out["Due Date"]["date"]["start"] == "2026-07-01"
    assert "Notes" not in out          # None skipped
    # a role with no column in the schema is skipped silently
    assert all(k in ("Name", "Status", "Due Date") for k in out)
