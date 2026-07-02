import json
from lifeos_mcp.mapctl import run

def test_push_then_pull_roundtrips(tmp_path):
    src = tmp_path / "local.json"; src.write_text(json.dumps({"k": "v"}), encoding="utf-8")
    maps = tmp_path / "maps"
    env = {"LIFEOS_MAP_STORE": "file", "LIFEOS_MAP_DIR": str(maps)}
    assert run(["push", "--identity", "111", "--file", str(src)], env) == 0
    assert (maps / "111.json").exists()
    out = tmp_path / "out.json"
    assert run(["pull", "--identity", "111", "--file", str(out)], env) == 0
    assert json.loads(out.read_text(encoding="utf-8")) == {"k": "v"}
