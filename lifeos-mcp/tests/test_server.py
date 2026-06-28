import copy
from datetime import date
from lifeos_mcp.server import build_app
from lifeos_mcp.config import Settings
from tests.fixtures.maps import FIXTURE_MAP
from tests.fakes import FakeNotionClient, FakeCalendarClient

def test_app_registers_five_tools(tmp_path):
    import json
    mp = tmp_path / "m.json"; mp.write_text(json.dumps(FIXTURE_MAP), encoding="utf-8")
    s = Settings(map_path=mp, notion_token="t", google_credentials="", google_token_path="")
    app = build_app(s, notion=FakeNotionClient(), calendar=FakeCalendarClient())
    names = {t.name for t in app._tool_manager.list_tools()}  # FastMCP registry
    assert {"get_today","get_week","query_records","add_record","create_event"} <= names
