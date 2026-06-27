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
