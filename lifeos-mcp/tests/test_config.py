import json
from pathlib import Path
from lifeos_mcp.config import load_map, save_map, load_settings

def test_load_and_save_roundtrip(tmp_path: Path):
    p = tmp_path / "m.json"
    data = {"workspace_root": "x", "areas": {}, "resolved": {"groups": {}}}
    save_map(data, p)
    assert load_map(p) == data
    assert "\n" in p.read_text(encoding="utf-8")  # pretty-printed

def test_load_settings_reads_env(tmp_path: Path):
    s = load_settings({
        "LIFEOS_MAP_PATH": str(tmp_path / "m.json"),
        "NOTION_TOKEN": "tok",
        "GOOGLE_OAUTH_CREDENTIALS": "creds.json",
        "GOOGLE_CALENDAR_MCP_TOKEN_PATH": "token.json",
    })
    assert s.notion_token == "tok"
    assert s.tz == "Europe/Berlin"
