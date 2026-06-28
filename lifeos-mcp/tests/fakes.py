from lifeos_mcp.errors import NotionNotFound

class FakeNotionClient:
    """In-memory NotionClient. children: {parent_id: [child dicts]};
    pages: {id: page dict}; rows: {data_source_id: [row dicts]};
    fail_with: {id: ErrorClass} to simulate stale/auth/transient."""
    def __init__(self, children=None, pages=None, rows=None, child_db=None, fail_with=None):
        self.children = children or {}
        self.pages = pages or {}
        self.rows = rows or {}
        self.child_db = child_db or {}      # {page_id: data_source_id}
        self.fail_with = fail_with or {}
        self.created = []
    def _maybe_fail(self, oid):
        if oid in self.fail_with:
            raise self.fail_with[oid](oid)
    def get_block_children(self, block_id):
        self._maybe_fail(block_id)
        return self.children.get(block_id, [])
    def retrieve(self, object_id):
        self._maybe_fail(object_id)
        if object_id not in self.pages:
            raise NotionNotFound(object_id)
        return self.pages[object_id]
    def find_tasks_db_under(self, page_id):
        self._maybe_fail(page_id)
        return self.child_db.get(page_id)
    def query_data_source(self, data_source_id, filter=None, sorts=None):
        self._maybe_fail(data_source_id)
        return self.rows.get(data_source_id, [])
    def create_page(self, data_source_id, properties):
        rec = {"id": f"new-{len(self.created)}", "url": "http://n/new", "properties": properties}
        self.created.append((data_source_id, properties))
        return rec

class FakeCalendarClient:
    def __init__(self, events=None):
        self.events = events or []
        self.created = []
        self.list_calls = []
    def list_events(self, time_min, time_max):
        self.list_calls.append((time_min, time_max))
        return self.events
    def create_event(self, title, start, end, notes=None):
        rec = {"id": f"ev-{len(self.created)}", "htmlLink": "http://cal/ev"}
        self.created.append((title, start, end, notes))
        return rec
