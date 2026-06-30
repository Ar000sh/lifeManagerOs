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

def test_build_props_typed_and_skips_none_and_relation():
    from lifeos_mcp.notion_client import build_props
    schema = {"role": "tasks",
              "title": {"col": "Name", "type": "title"},
              "due_date": {"col": "Due Date", "type": "date"},
              "fields": {"status": {"col": "Status", "type": "status"},
                         "module": {"col": "Module", "type": "relation"},
                         "notes": {"col": "Notes", "type": "rich_text"}}}
    out = build_props(schema, {"title": "Buy soap", "status": "Open",
                               "due_date": "2026-07-01", "module": ["mod-1"],
                               "notes": None, "missing_role": "x"})
    assert out["Name"]["title"][0]["text"]["content"] == "Buy soap"
    assert out["Status"]["status"]["name"] == "Open"
    assert out["Due Date"]["date"]["start"] == "2026-07-01"
    assert out["Module"]["relation"] == [{"id": "mod-1"}]
    assert "Notes" not in out                       # None skipped
    assert "missing_role" not in out and len(out) == 4

def test_extract_props_reads_multiselect_people_url_email_phone():
    page = {"properties": {
        "Tags": {"type": "multi_select", "multi_select": [{"name": "a"}, {"name": "b"}]},
        "Assignee": {"type": "people", "people": [{"id": "u-1"}, {"id": "u-2"}]},
        "Link": {"type": "url", "url": "https://x.test"},
        "Contact": {"type": "email", "email": "a@b.com"},
        "Phone": {"type": "phone_number", "phone_number": "+49123"}}}
    props = extract_props(page)
    assert props["Tags"] == ["a", "b"]
    assert props["Assignee"] == ["u-1", "u-2"]
    assert props["Link"] == "https://x.test"
    assert props["Contact"] == "a@b.com"
    assert props["Phone"] == "+49123"

def test_build_props_builds_multiselect_people_url_email_phone():
    from lifeos_mcp.notion_client import build_props
    schema = {"role": "tasks",
              "title": {"col": "Name", "type": "title"},
              "fields": {"tags": {"col": "Tags", "type": "multi_select"},
                         "assignee": {"col": "Assignee", "type": "people"},
                         "link": {"col": "Link", "type": "url"},
                         "contact": {"col": "Contact", "type": "email"},
                         "phone": {"col": "Phone", "type": "phone_number"}}}
    out = build_props(schema, {"title": "T", "tags": ["a", "b"], "assignee": ["u-1"],
                               "link": "https://x.test", "contact": "a@b.com", "phone": "+49123"})
    assert out["Tags"]["multi_select"] == [{"name": "a"}, {"name": "b"}]
    assert out["Assignee"]["people"] == [{"id": "u-1"}]
    assert out["Link"]["url"] == "https://x.test"
    assert out["Contact"]["email"] == "a@b.com"
    assert out["Phone"]["phone_number"] == "+49123"

def test_build_props_raises_on_declared_unsupported_type():
    from lifeos_mcp.notion_client import build_props
    from lifeos_mcp.errors import UnsupportedFieldType
    schema = {"role": "tasks",
              "title": {"col": "Name", "type": "title"},
              "fields": {"calc": {"col": "Calc", "type": "formula"}}}
    # a declared field with an unsupported type + a real value fails loud, not silently dropped
    with pytest.raises(UnsupportedFieldType):
        build_props(schema, {"title": "T", "calc": 5})

def test_build_props_unsupported_type_with_none_value_is_skipped():
    from lifeos_mcp.notion_client import build_props
    schema = {"role": "tasks",
              "title": {"col": "Name", "type": "title"},
              "fields": {"calc": {"col": "Calc", "type": "formula"}}}
    # None value is skipped before the type check -> no raise (nothing to write)
    out = build_props(schema, {"title": "T", "calc": None})
    assert "Calc" not in out
