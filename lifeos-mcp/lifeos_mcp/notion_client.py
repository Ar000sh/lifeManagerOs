from typing import Protocol
import httpx
from .errors import NotionNotFound, NotionAuthError, TransientError, UnsupportedFieldType
from .resolver_schema import field_def

class NotionClient(Protocol):
    def get_block_children(self, block_id: str) -> list[dict]: ...
    def retrieve(self, object_id: str) -> dict: ...
    def find_tasks_db_under(self, page_id: str) -> str | None: ...
    def query_data_source(self, data_source_id: str, filter=None, sorts=None) -> list[dict]: ...
    def create_page(self, data_source_id: str, properties: dict) -> dict: ...

def _raise_for_status(resp: httpx.Response):
    if resp.status_code == 404: raise NotionNotFound(resp.url.path)
    if resp.status_code in (401, 403): raise NotionAuthError(str(resp.status_code))
    if resp.status_code == 429 or resp.status_code >= 500: raise TransientError(str(resp.status_code))
    resp.raise_for_status()

def extract_props(page: dict) -> dict:
    out = {}
    for name, v in page.get("properties", {}).items():
        t = v.get("type")
        if t in ("select", "status"):
            out[name] = (v.get(t) or {}).get("name")
        elif t == "checkbox":
            out[name] = v.get("checkbox")
        elif t == "date":
            out[name] = (v.get("date") or {}).get("start")
        elif t == "title":
            out[name] = "".join(x.get("plain_text", "") for x in v.get("title", []))
        elif t == "rich_text":
            out[name] = "".join(x.get("plain_text", "") for x in v.get("rich_text", []))
        elif t == "number":
            out[name] = v.get("number")
        elif t == "relation":
            out[name] = [r.get("id") for r in v.get("relation", [])]
        elif t == "multi_select":
            out[name] = [o.get("name") for o in v.get("multi_select", [])]
        elif t == "people":
            out[name] = [p.get("id") for p in v.get("people", [])]
        elif t in ("url", "email", "phone_number"):
            out[name] = v.get(t)
    return out

TYPE_BUILDERS = {
    "title":        lambda v: {"title": [{"text": {"content": str(v)}}]},
    "date":         lambda v: {"date": {"start": str(v)}},
    "select":       lambda v: {"select": {"name": str(v)}},
    "status":       lambda v: {"status": {"name": str(v)}},
    "checkbox":     lambda v: {"checkbox": bool(v)},
    "number":       lambda v: {"number": v},
    "relation":     lambda v: {"relation": [{"id": i} for i in v]},
    "rich_text":    lambda v: {"rich_text": [{"text": {"content": str(v)}}]},
    "multi_select": lambda v: {"multi_select": [{"name": str(n)} for n in v]},
    "people":       lambda v: {"people": [{"id": i} for i in v]},
    "url":          lambda v: {"url": str(v)},
    "email":        lambda v: {"email": str(v)},
    "phone_number": lambda v: {"phone_number": str(v)},
}

# The engine's authoritative set of field types it can read and write.
SUPPORTED_TYPES = frozenset(TYPE_BUILDERS)

def build_props(schema: dict, fields: dict) -> dict:
    """Build Notion property payloads from each field's declared type.

    A declared field carrying a real value whose type has no builder is a map
    misconfiguration: raise rather than silently dropping the value."""
    props = {}
    for key, value in fields.items():
        d = field_def(schema, key)
        if not d or value is None:
            continue
        builder = TYPE_BUILDERS.get(d.get("type"))
        if builder is None:
            raise UnsupportedFieldType(
                f"field {key!r} (column {d.get('col')!r}) declares unsupported "
                f"type {d.get('type')!r}")
        props[d["col"]] = builder(value)
    return props

class HttpxNotionClient:
    def __init__(self, token: str, api_version: str = "2022-06-28"):
        self._http = httpx.Client(
            base_url="https://api.notion.com",
            headers={"Authorization": f"Bearer {token}",
                     "Notion-Version": api_version,
                     "Content-Type": "application/json"}, timeout=30.0)

    def get_block_children(self, block_id: str) -> list[dict]:
        r = self._http.get(f"/v1/blocks/{block_id}/children?page_size=100")
        _raise_for_status(r)
        out = []
        for b in r.json().get("results", []):
            if b.get("type") == "child_page":
                out.append({"id": b["id"], "title": b["child_page"]["title"]})
            elif b.get("type") == "child_database":
                out.append({"id": b["id"], "title": b["child_database"]["title"], "is_db": True})
        return out

    def retrieve(self, object_id: str) -> dict:
        r = self._http.get(f"/v1/pages/{object_id}")
        if r.status_code == 404:
            r = self._http.get(f"/v1/databases/{object_id}")
        _raise_for_status(r)
        return r.json()

    def find_tasks_db_under(self, page_id: str) -> str | None:
        for child in self.get_block_children(page_id):
            if child.get("is_db"):
                return child["id"]
        return None

    def query_data_source(self, data_source_id: str, filter=None, sorts=None) -> list[dict]:
        body = {}
        if filter: body["filter"] = filter
        if sorts: body["sorts"] = sorts
        r = self._http.post(f"/v1/databases/{data_source_id}/query", json=body)
        _raise_for_status(r)
        return r.json().get("results", [])

    def create_page(self, data_source_id: str, properties: dict) -> dict:
        r = self._http.post("/v1/pages",
                            json={"parent": {"database_id": data_source_id}, "properties": properties})
        _raise_for_status(r)
        return r.json()
