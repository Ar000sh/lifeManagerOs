from typing import Protocol
import httpx
from .errors import NotionNotFound, NotionAuthError, TransientError

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

def _title_of(page: dict) -> str:
    for v in page.get("properties", {}).values():
        if v.get("type") == "title":
            return "".join(t.get("plain_text", "") for t in v.get("title", []))
    return page.get("id", "")

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
    return out

def build_props(schema: dict, fields: dict) -> dict:
    """Map python field values -> Notion property payloads using the schema."""
    props = {}
    for role, value in fields.items():
        col = schema.get(role)
        if not col or value is None:
            continue
        if role == "title":
            props[col] = {"title": [{"text": {"content": str(value)}}]}
        elif role in ("status",):
            props[col] = {"select": {"name": str(value)}}
        elif role == "priority":
            props[col] = {"select": {"name": str(value)}}
        elif role in ("due_date", "exam_date"):
            props[col] = {"date": {"start": str(value)}}
        else:
            props[col] = {"rich_text": [{"text": {"content": str(value)}}]}
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
