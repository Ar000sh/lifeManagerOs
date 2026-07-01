# Phase B Foundation — Identity-Keyed Persistence & Bot Wiring (Plan 1 of 2)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Give the `lifeos` MCP server an identity-keyed map store (Telegram chat id → user id later), backed by a local file store in dev and Azure Blob in prod, and register the server programmatically in the Telegram bot — so a blob-backed map per identity flows end-to-end.

**Architecture:** A `MapStore` abstraction (`load(identity)`/`save(identity, data)`) replaces the server's hard-coded map path. `FileMapStore` for dev, `AzureBlobMapStore` (auth via the VM's system-assigned managed identity, lazy Azure imports) for prod. `config.build_store()` picks the backend from env. `server.py` tools load/save per identity. A `mapctl` CLI moves a local map file in/out of the store. New `infra/storage.tf` provisions the account + `maps` container + `Storage Blob Data Contributor` role for the VM identity. `agent_runner.build_options()` registers lifeos as a third stdio MCP server and threads the chat id as `LIFEOS_IDENTITY`.

**Tech Stack:** Python 3.10, dataclasses, httpx, `azure-identity`, `azure-storage-blob`, pytest. FastMCP. Terraform (azurerm). Claude Agent SDK.

**Spec:** `lifeos-mcp/docs/superpowers/specs/2026-07-01-phase-b-bot-integration-design.md`. Plan 2 (refresh-notion rewrite + thin skills + live validation) follows separately.

## Global Constraints

- Run lifeos-mcp tests from `lifeos-mcp/`: full suite `../telegram-bot/.venv/Scripts/python.exe -m pytest -q`; targeted `… -m pytest tests/<file>.py -q`. Baseline is **98 passing**; keep green at every task boundary.
- Commit-per-task on branch `feat/dynamic-skills`, **local, no push**. End every commit message with:
  `Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>`
- TDD: write the failing test first, watch it fail, implement minimally, watch it pass, commit.
- Store key (`identity`) is the Telegram **chat id** now; the interface must not assume it is (a plain `str`), so swapping to a user id later is a value change only.
- Azure SDK imports must be **lazy** (inside methods), mirroring `calendar_client.py`, so dev/tests run without `azure-*` installed.
- Infra: Claude writes `.tf` + its `infra/doc/*.md` and the commands; **Aroosh** runs `terraform` (plan/apply ships through the gated CI/CD pipeline). Never run `terraform apply` on his behalf.

---

## File Structure

- `lifeos_mcp/map_store.py` — **new.** `MapStore` protocol, `FileMapStore`, `AzureBlobMapStore`.
- `lifeos_mcp/errors.py` — add `MapNotFound`.
- `lifeos_mcp/config.py` — `Settings` gains `identity` + store selection; add `build_store(settings)`. `load_map`/`save_map` kept (used by `mapctl`).
- `lifeos_mcp/server.py` — tools call `store.load/save(identity)`; map-missing → `{"error": "no_map"}`.
- `lifeos_mcp/mapctl.py` — **new.** `python -m lifeos_mcp.mapctl push|pull` between a local file and the store.
- `lifeos_mcp/pyproject.toml` — add `azure-identity`, `azure-storage-blob`.
- `infra/storage.tf` + `infra/doc/storage.tf.md` — **new.** App-data storage account, `maps` container, VM role assignment.
- `infra/outputs.tf` — add the blob endpoint output.
- `telegram-bot/agent_runner.py` — register `lifeos` server, thread `chat_id`, allow `mcp__lifeos`.
- `telegram-bot/bot.py` — pass `chat_id` into `run_agent`.
- Tests: `tests/test_map_store.py`, `tests/test_config_store.py`, `tests/test_edgecases_review.py` (update Task 21), `tests/test_mapctl.py`; `telegram-bot/tests/test_agent_runner_lifeos.py`.

---

### Task 1: `MapStore` protocol + `FileMapStore` + `MapNotFound`

**Files:**
- Create: `lifeos_mcp/map_store.py`
- Modify: `lifeos_mcp/errors.py`
- Test: `tests/test_map_store.py`

**Interfaces:**
- Produces: `MapNotFound(LifeOsError)`; `class FileMapStore` with `__init__(base_dir: str | Path)`, `load(identity: str) -> dict` (raises `MapNotFound` if absent), `save(identity: str, data: dict) -> None` (creates `base_dir`, writes `{identity}.json` pretty UTF-8). `MapStore` Protocol with `load`/`save`.

- [ ] **Step 1: Write the failing test**

Create `tests/test_map_store.py`:

```python
import pytest
from lifeos_mcp.map_store import FileMapStore
from lifeos_mcp.errors import MapNotFound

def test_file_store_round_trips_by_identity(tmp_path):
    store = FileMapStore(tmp_path / "maps")
    store.save("111", {"hello": "world"})
    assert store.load("111") == {"hello": "world"}

def test_file_store_isolates_identities(tmp_path):
    store = FileMapStore(tmp_path / "maps")
    store.save("111", {"who": "a"})
    store.save("222", {"who": "b"})
    assert store.load("222") == {"who": "b"}

def test_file_store_missing_identity_raises(tmp_path):
    store = FileMapStore(tmp_path / "maps")
    with pytest.raises(MapNotFound):
        store.load("nope")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `../telegram-bot/.venv/Scripts/python.exe -m pytest tests/test_map_store.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'lifeos_mcp.map_store'`.

- [ ] **Step 3: Add `MapNotFound`**

In `lifeos_mcp/errors.py`, after `UnsupportedFieldType`:

```python
class MapNotFound(LifeOsError): ...
```

- [ ] **Step 4: Create `map_store.py` with `FileMapStore`**

```python
import json
from pathlib import Path
from typing import Protocol
from .errors import MapNotFound


class MapStore(Protocol):
    def load(self, identity: str) -> dict: ...
    def save(self, identity: str, data: dict) -> None: ...


class FileMapStore:
    """Local dev: one JSON file per identity under base_dir."""

    def __init__(self, base_dir):
        self.base_dir = Path(base_dir)

    def _path(self, identity: str) -> Path:
        return self.base_dir / f"{identity}.json"

    def load(self, identity: str) -> dict:
        p = self._path(identity)
        if not p.exists():
            raise MapNotFound(identity)
        return json.loads(p.read_text(encoding="utf-8"))

    def save(self, identity: str, data: dict) -> None:
        self.base_dir.mkdir(parents=True, exist_ok=True)
        self._path(identity).write_text(
            json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `../telegram-bot/.venv/Scripts/python.exe -m pytest tests/test_map_store.py -q`
Expected: PASS (3 tests).

- [ ] **Step 6: Commit**

```bash
git add lifeos_mcp/map_store.py lifeos_mcp/errors.py tests/test_map_store.py
git commit -m "feat(lifeos-mcp): FileMapStore + MapNotFound (identity-keyed map store)

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 2: `AzureBlobMapStore` (lazy Azure, fake-client tests) + deps

**Files:**
- Modify: `lifeos_mcp/map_store.py`, `lifeos_mcp/pyproject.toml`
- Test: `tests/test_map_store.py`

**Interfaces:**
- Produces: `class AzureBlobMapStore` with `__init__(account_url: str, container: str, credential=None, container_client=None)`, `load(identity)` (raises `MapNotFound` when the blob is absent — detected by exception class name `ResourceNotFoundError`, so no Azure import in tests), `save(identity, data)` (`overwrite=True`). `container_client` is injectable for tests.

- [ ] **Step 1: Write the failing test (fake container client, no Azure needed)**

Add to `tests/test_map_store.py`:

```python
class _ResourceNotFoundError(Exception):
    pass

class _FakeBlob:
    def __init__(self, store, name):
        self._store, self._name = store, name
    def download_blob(self):
        if self._name not in self._store:
            raise _ResourceNotFoundError(self._name)
        data = self._store[self._name]
        class _D:
            def readall(_self):
                return data
        return _D()
    def upload_blob(self, payload, overwrite=False):
        self._store[self._name] = payload

class _FakeContainerClient:
    def __init__(self):
        self.blobs = {}
    def get_blob_client(self, name):
        return _FakeBlob(self.blobs, name)

def test_blob_store_save_then_load():
    from lifeos_mcp.map_store import AzureBlobMapStore
    cc = _FakeContainerClient()
    store = AzureBlobMapStore("https://acct.blob.core.windows.net", "maps", container_client=cc)
    store.save("111", {"k": "v"})
    assert store.load("111") == {"k": "v"}
    assert "111.json" in cc.blobs

def test_blob_store_missing_raises_mapnotfound():
    from lifeos_mcp.map_store import AzureBlobMapStore
    from lifeos_mcp.errors import MapNotFound
    store = AzureBlobMapStore("https://acct.blob.core.windows.net", "maps",
                              container_client=_FakeContainerClient())
    with pytest.raises(MapNotFound):
        store.load("missing")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `../telegram-bot/.venv/Scripts/python.exe -m pytest tests/test_map_store.py::test_blob_store_save_then_load -q`
Expected: FAIL — `ImportError: cannot import name 'AzureBlobMapStore'`.

- [ ] **Step 3: Add `AzureBlobMapStore` (lazy Azure imports)**

Append to `lifeos_mcp/map_store.py`:

```python
class AzureBlobMapStore:
    """Production: blob `{identity}.json` in a container. Auth via DefaultAzureCredential
    (the VM's managed identity). Azure libs are imported lazily so dev/tests don't need them."""

    def __init__(self, account_url: str, container: str, credential=None, container_client=None):
        self._account_url = account_url
        self._container_name = container
        self._credential = credential
        self._cc = container_client  # injectable for tests

    def _container(self):
        if self._cc is None:
            from azure.identity import DefaultAzureCredential
            from azure.storage.blob import BlobServiceClient
            cred = self._credential or DefaultAzureCredential()
            svc = BlobServiceClient(account_url=self._account_url, credential=cred)
            self._cc = svc.get_container_client(self._container_name)
        return self._cc

    def load(self, identity: str) -> dict:
        blob = self._container().get_blob_client(f"{identity}.json")
        try:
            data = blob.download_blob().readall()
        except Exception as exc:  # duck-typed: Azure raises ResourceNotFoundError
            if type(exc).__name__ == "ResourceNotFoundError":
                raise MapNotFound(identity) from exc
            raise
        return json.loads(data)

    def save(self, identity: str, data: dict) -> None:
        blob = self._container().get_blob_client(f"{identity}.json")
        blob.upload_blob(
            json.dumps(data, indent=2, ensure_ascii=False).encode("utf-8"), overwrite=True)
```

- [ ] **Step 4: Add Azure deps**

In `lifeos_mcp/pyproject.toml`, add to `dependencies`:

```toml
  "azure-identity>=1.15",
  "azure-storage-blob>=12.19",
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `../telegram-bot/.venv/Scripts/python.exe -m pytest tests/test_map_store.py -q`
Expected: PASS (5 tests).

- [ ] **Step 6: Commit**

```bash
git add lifeos_mcp/map_store.py lifeos_mcp/pyproject.toml tests/test_map_store.py
git commit -m "feat(lifeos-mcp): AzureBlobMapStore (lazy azure, managed-identity auth)

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 3: `Settings` identity + store selection + `build_store`

**Files:**
- Modify: `lifeos_mcp/config.py`
- Test: `tests/test_config_store.py`

**Interfaces:**
- Consumes: `FileMapStore`, `AzureBlobMapStore` (Tasks 1–2).
- Produces: `Settings` fields `identity: str`, `map_store: str` (`"file"`|`"blob"`), `map_dir: str`, `blob_account_url: str`, `map_container: str` (plus existing `notion_token`, `google_credentials`, `google_token_path`, `tz`). `load_settings(env)` reads `LIFEOS_IDENTITY`, `LIFEOS_MAP_STORE` (default `"file"`), `LIFEOS_MAP_DIR` (default `<repo>/context/maps`), `LIFEOS_BLOB_ACCOUNT_URL`, `LIFEOS_MAP_CONTAINER` (default `"maps"`). `build_store(settings) -> MapStore` returns `AzureBlobMapStore` when `map_store == "blob"`, else `FileMapStore`.

- [ ] **Step 1: Write the failing test**

Create `tests/test_config_store.py`:

```python
from lifeos_mcp.config import load_settings, build_store
from lifeos_mcp.map_store import FileMapStore, AzureBlobMapStore

def test_defaults_to_file_store():
    s = load_settings({"LIFEOS_IDENTITY": "111"})
    assert s.identity == "111"
    assert s.map_store == "file"
    assert isinstance(build_store(s), FileMapStore)

def test_blob_selected_by_env():
    s = load_settings({"LIFEOS_IDENTITY": "111", "LIFEOS_MAP_STORE": "blob",
                       "LIFEOS_BLOB_ACCOUNT_URL": "https://acct.blob.core.windows.net",
                       "LIFEOS_MAP_CONTAINER": "maps"})
    store = build_store(s)
    assert isinstance(store, AzureBlobMapStore)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `../telegram-bot/.venv/Scripts/python.exe -m pytest tests/test_config_store.py -q`
Expected: FAIL — `ImportError: cannot import name 'build_store'` (and `Settings` has no `identity`).

- [ ] **Step 3: Rewrite `config.py` Settings + add `build_store`**

Replace the `Settings` dataclass and `load_settings`, keep `load_map`/`save_map`, add `build_store`:

```python
import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping
from .map_store import FileMapStore, AzureBlobMapStore

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_DEFAULT_MAP_DIR = _REPO_ROOT / "context" / "maps"

def load_map(path) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))

def save_map(data: dict, path) -> None:
    Path(path).write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")

@dataclass
class Settings:
    identity: str
    notion_token: str
    google_credentials: str
    google_token_path: str
    map_store: str = "file"
    map_dir: str = str(_DEFAULT_MAP_DIR)
    blob_account_url: str = ""
    map_container: str = "maps"
    tz: str = "Europe/Berlin"

def load_settings(env: Mapping[str, str] | None = None) -> Settings:
    env = env if env is not None else os.environ
    return Settings(
        identity=env.get("LIFEOS_IDENTITY", "").strip(),
        notion_token=env.get("NOTION_TOKEN", "").strip(),
        google_credentials=env.get("GOOGLE_OAUTH_CREDENTIALS", "").strip(),
        google_token_path=env.get("GOOGLE_CALENDAR_MCP_TOKEN_PATH", "").strip(),
        map_store=env.get("LIFEOS_MAP_STORE", "file").strip() or "file",
        map_dir=env.get("LIFEOS_MAP_DIR", str(_DEFAULT_MAP_DIR)),
        blob_account_url=env.get("LIFEOS_BLOB_ACCOUNT_URL", "").strip(),
        map_container=env.get("LIFEOS_MAP_CONTAINER", "maps").strip() or "maps",
        tz=env.get("LIFEOS_TZ", "Europe/Berlin").strip() or "Europe/Berlin",
    )

def build_store(settings: Settings):
    if settings.map_store == "blob":
        return AzureBlobMapStore(settings.blob_account_url, settings.map_container)
    return FileMapStore(settings.map_dir)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `../telegram-bot/.venv/Scripts/python.exe -m pytest tests/test_config_store.py -q`
Expected: PASS (2 tests).

- [ ] **Step 5: Commit**

```bash
git add lifeos_mcp/config.py tests/test_config_store.py
git commit -m "feat(lifeos-mcp): Settings identity + store selection + build_store

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 4: `server.py` uses the store per identity; map-missing → `no_map`

**Files:**
- Modify: `lifeos_mcp/server.py`
- Test: `tests/test_edgecases_review.py` (update the server test to the new `Settings`/store; add a `no_map` test), `tests/test_server.py` (update `Settings(...)` call — it passed `map_path`)

**Interfaces:**
- Consumes: `build_store`, `Settings`, `MapNotFound`.
- Produces: each tool loads `settings.identity`'s map via the store, runs, saves it back; `get_today`/`get_week` return `{"error": "no_map"}` on `MapNotFound` and `{"error": "reconnect_notion"}` on `WorkspaceUnavailable`.

- [ ] **Step 1: Update the existing server test + add a `no_map` test**

In `tests/test_edgecases_review.py`, replace the body of `test_server_today_reconnect_on_workspace_unavailable` so it builds a `FileMapStore`-backed settings and identity, then add a `no_map` test:

```python
def test_server_today_reconnect_on_workspace_unavailable(tmp_path):
    import json
    from lifeos_mcp.config import Settings
    from lifeos_mcp.server import build_app
    from lifeos_mcp.errors import NotionAuthError

    m = copy.deepcopy(FIXTURE_MAP)
    m["resolved"]["groups"]["ventures"]["second-page"] = {
        "label": "Two", "role": "tasks", "tasks_db": "two-db", "cached_at": "2026-06-26"}
    maps_dir = tmp_path / "maps"; maps_dir.mkdir()
    (maps_dir / "111.json").write_text(json.dumps(m), encoding="utf-8")

    notion = FakeNotionClient(children={"biz-root": []},
        fail_with={"laundro-page": NotionAuthError, "second-page": NotionAuthError})
    settings = Settings(identity="111", notion_token="t", google_credentials="{}",
                        google_token_path="/x", map_store="file", map_dir=str(maps_dir),
                        tz="Europe/Berlin")
    app = build_app(settings, notion=notion, calendar=FakeCalendarClient())
    fn = app._tool_manager.get_tool("get_today").fn
    assert fn() == {"error": "reconnect_notion"}
    assert json.loads((maps_dir / "111.json").read_text()) == m   # not half-reconciled

def test_server_today_no_map_when_identity_absent(tmp_path):
    from lifeos_mcp.config import Settings
    from lifeos_mcp.server import build_app
    settings = Settings(identity="999", notion_token="t", google_credentials="{}",
                        google_token_path="/x", map_store="file",
                        map_dir=str(tmp_path / "maps"), tz="Europe/Berlin")
    app = build_app(settings, notion=FakeNotionClient(), calendar=FakeCalendarClient())
    assert app._tool_manager.get_tool("get_today").fn() == {"error": "no_map"}
```

- [ ] **Step 2: Update `tests/test_server.py` (it constructs `Settings(map_path=...)`)**

Replace the `Settings(...)` line in `test_app_registers_five_tools`:

```python
    s = Settings(identity="1", notion_token="t", google_credentials="", google_token_path="",
                 map_store="file", map_dir=str(tmp_path / "maps"))
```

(It only checks tool registration, so no map file is needed.)

- [ ] **Step 3: Run to verify failure**

Run: `../telegram-bot/.venv/Scripts/python.exe -m pytest tests/test_edgecases_review.py -k server tests/test_server.py -q`
Expected: FAIL — `get_today` doesn't return `no_map` yet (server still uses the old `settings.map_path`).

- [ ] **Step 4: Rewrite `server.py` to use the store**

Replace imports and the tool bodies (`build_app`), keeping tool names/signatures:

```python
from datetime import datetime
from zoneinfo import ZoneInfo
from mcp.server.fastmcp import FastMCP
from .config import Settings, load_settings, build_store
from .errors import WorkspaceUnavailable, MapNotFound
from .notion_client import HttpxNotionClient
from .calendar_client import GoogleCalendarClient
from .tools.get_today import get_today
from .tools.get_week import get_week
from .tools.query_records import query_records
from .tools.add_record import add_record
from .tools.create_event import create_event


def build_app(settings: Settings, notion=None, calendar=None) -> FastMCP:
    app = FastMCP("lifeos")
    store = build_store(settings)

    def _notion():
        return notion or HttpxNotionClient(settings.notion_token)

    def _calendar():
        return calendar or GoogleCalendarClient(
            settings.google_credentials, settings.google_token_path, settings.tz)

    def _today():
        return datetime.now(ZoneInfo(settings.tz)).date()

    @app.tool(name="get_today")
    def get_today_tool() -> dict:
        """Today's tasks, key dates, work shift, and calendar events across all areas."""
        try:
            m = store.load(settings.identity)
        except MapNotFound:
            return {"error": "no_map"}
        try:
            payload = get_today(m, _notion(), _calendar(), _today(), settings.tz)
        except WorkspaceUnavailable:
            return {"error": "reconnect_notion"}
        store.save(settings.identity, m)
        return payload.to_dict()

    @app.tool(name="get_week")
    def get_week_tool() -> dict:
        """This week's tasks, deadlines, shifts, and events (Mon-Sun)."""
        try:
            m = store.load(settings.identity)
        except MapNotFound:
            return {"error": "no_map"}
        try:
            payload = get_week(m, _notion(), _calendar(), _today(), settings.tz)
        except WorkspaceUnavailable:
            return {"error": "reconnect_notion"}
        store.save(settings.identity, m)
        return payload.to_dict()

    @app.tool(name="query_records")
    def query_records_tool(role: str, filters: dict | None = None) -> list:
        """Query records of a function role (tasks/schedule/catalog) with optional filters."""
        try:
            m = store.load(settings.identity)
        except MapNotFound:
            return []
        res = query_records(m, _notion(), role, filters)
        store.save(settings.identity, m)
        return res

    @app.tool(name="add_record")
    def add_record_tool(role: str, fields: dict, area: str | None = None) -> dict:
        """Create a record (row) of a role into its resolved destination. Records only."""
        try:
            m = store.load(settings.identity)
        except MapNotFound:
            return {"created": False, "error": "no_map"}
        res = add_record(m, _notion(), role, fields, area)
        store.save(settings.identity, m)
        return res

    @app.tool(name="create_event")
    def create_event_tool(title: str, start: str, end: str | None = None, notes: str | None = None) -> dict:
        """Create a Google Calendar event (Europe/Berlin, default 1h)."""
        return create_event(_calendar(), title, start, end, notes)

    return app


def main():
    build_app(load_settings()).run()


if __name__ == "__main__":
    main()
```

- [ ] **Step 5: Run the full suite**

Run: `../telegram-bot/.venv/Scripts/python.exe -m pytest -q`
Expected: PASS (98 prior + new store/config/server tests).

- [ ] **Step 6: Commit**

```bash
git add lifeos_mcp/server.py tests/test_edgecases_review.py tests/test_server.py
git commit -m "feat(lifeos-mcp): server loads/saves map per identity via MapStore; no_map error

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 5: `mapctl` — push/pull a local map file to/from the store

**Files:**
- Create: `lifeos_mcp/mapctl.py`
- Test: `tests/test_mapctl.py`

**Interfaces:**
- Consumes: `build_store`, `load_settings`, `load_map`, `save_map`.
- Produces: `run(argv: list[str], env: Mapping | None = None) -> int`. `push --identity <id> --file <path>` uploads the local JSON to the store; `pull --identity <id> --file <path>` writes the store's map to the local path. `python -m lifeos_mcp.mapctl` calls `run(sys.argv[1:])`.

- [ ] **Step 1: Write the failing test (file store, tmp dir)**

Create `tests/test_mapctl.py`:

```python
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
```

- [ ] **Step 2: Run to verify failure**

Run: `../telegram-bot/.venv/Scripts/python.exe -m pytest tests/test_mapctl.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'lifeos_mcp.mapctl'`.

- [ ] **Step 3: Create `mapctl.py`**

```python
import argparse
import sys
from .config import load_settings, build_store, load_map, save_map


def run(argv, env=None) -> int:
    parser = argparse.ArgumentParser(prog="mapctl")
    sub = parser.add_subparsers(dest="cmd", required=True)
    for name in ("push", "pull"):
        p = sub.add_parser(name)
        p.add_argument("--identity", required=True)
        p.add_argument("--file", required=True)
    args = parser.parse_args(argv)

    settings = load_settings(env)
    store = build_store(settings)
    if args.cmd == "push":
        store.save(args.identity, load_map(args.file))
    else:  # pull
        save_map(store.load(args.identity), args.file)
    return 0


def main() -> int:
    return run(sys.argv[1:])


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `../telegram-bot/.venv/Scripts/python.exe -m pytest tests/test_mapctl.py -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add lifeos_mcp/mapctl.py tests/test_mapctl.py
git commit -m "feat(lifeos-mcp): mapctl push/pull a map file to/from the store

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 6: Infra — `storage.tf` + doc + output

**Files:**
- Create: `infra/storage.tf`, `infra/doc/storage.tf.md`
- Modify: `infra/outputs.tf`, `infra/doc/outputs.tf.md`

**Interfaces:**
- Produces: an app-data storage account (random-suffixed name), private `maps` container, and a `Storage Blob Data Contributor` role assignment for the VM's system-assigned identity; an output `maps_blob_endpoint`.

*No unit test — Terraform. Validate with `terraform validate`/`plan`; Aroosh applies via the CI/CD pipeline. Claude does NOT run apply.*

- [ ] **Step 1: Create `infra/storage.tf`**

```hcl
# App-data storage: holds one Life-OS map blob per identity (Telegram chat id -> user id).
# Separate from the Terraform-state account (least privilege, different lifecycle).

resource "random_string" "storage_suffix" {
  length  = 6
  upper   = false
  special = false
}

resource "azurerm_storage_account" "data" {
  name                     = "st${var.prefix}data${random_string.storage_suffix.result}"
  resource_group_name      = azurerm_resource_group.main.name
  location                 = azurerm_resource_group.main.location
  account_tier             = "Standard"
  account_replication_type = "LRS"
  min_tls_version          = "TLS1_2"
}

resource "azurerm_storage_container" "maps" {
  name                  = "maps"
  storage_account_id    = azurerm_storage_account.data.id
  container_access_type = "private"
}

# The VM identity may READ+WRITE map blobs (data-plane RBAC, no account keys).
resource "azurerm_role_assignment" "vm_storage" {
  scope                = azurerm_storage_account.data.id
  role_definition_name = "Storage Blob Data Contributor"
  principal_id         = azurerm_linux_virtual_machine.main.identity[0].principal_id
}
```

- [ ] **Step 2: Add the output**

In `infra/outputs.tf`, append:

```hcl
output "maps_blob_endpoint" {
  description = "Blob endpoint for the app-data account (set as LIFEOS_BLOB_ACCOUNT_URL)."
  value       = azurerm_storage_account.data.primary_blob_endpoint
}
```

- [ ] **Step 3: Write `infra/doc/storage.tf.md`** (beginner-friendly, per the docs rule)

```markdown
# storage.tf — App-data storage for Life-OS maps

**What this file is for.** Somewhere durable to keep each user's Life-OS *map*
(`{identity}.json`). The bot's `lifeos` MCP server reads/writes it every call. Using Azure
Blob (not a file on the VM) means the map survives a VM rebuild. AWS parallel: an **S3
bucket** + an object per user, with the VM's IAM role granted access.

## Resources

- **`random_string.storage_suffix`** — storage account names are globally unique and allow
  only lowercase letters/digits. We append 6 random chars so `st<prefix>data<suffix>` won't
  collide. (Same trick the tfstate account uses.)
- **`azurerm_storage_account.data`** — the account (like an S3 *namespace*).
  - `account_tier = "Standard"`, `account_replication_type = "LRS"` — cheapest durable option
    (locally redundant). `min_tls_version = "TLS1_2"` — refuse old TLS.
- **`azurerm_storage_container.maps`** — a container (like an S3 *bucket path*) named `maps`,
  `private` (no anonymous access).
- **`azurerm_role_assignment.vm_storage`** — grants the VM's **managed identity** the
  `Storage Blob Data Contributor` role on this account: read+write blobs with **no keys or
  connection strings** (AWS parallel: attaching an S3 read/write policy to the instance role).
  Mirrors the existing `vm_kv` (Key Vault) and `vm_acr` (registry) grants in `vm.tf`.

## How the app uses it

The server authenticates with `DefaultAzureCredential`, which on the VM picks up the managed
identity automatically. It's told the account via `LIFEOS_BLOB_ACCOUNT_URL`
(= the `maps_blob_endpoint` output) and the container via `LIFEOS_MAP_CONTAINER=maps`.

## Applying

Ships through the gated pipeline: push to `main` runs `terraform plan`; approve the
`production` environment to apply. Never `terraform apply` locally for this file.
```

- [ ] **Step 4: Note the output doc**

In `infra/doc/outputs.tf.md`, add a line documenting `maps_blob_endpoint` (the blob endpoint the bot reads as `LIFEOS_BLOB_ACCOUNT_URL`).

- [ ] **Step 5: Validate (Aroosh runs; Claude prepares)**

Command for Aroosh: `cd infra && terraform validate` then `terraform plan`. Expected: plan adds `azurerm_storage_account.data`, `azurerm_storage_container.maps`, `azurerm_role_assignment.vm_storage`, `random_string.storage_suffix`, and the output — no changes to existing resources.

- [ ] **Step 6: Commit**

```bash
git add infra/storage.tf infra/outputs.tf infra/doc/storage.tf.md infra/doc/outputs.tf.md
git commit -m "feat(infra): app-data storage account + maps container + VM blob role

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 7: Wire `lifeos` into the bot (programmatic MCP + identity threading)

**Files:**
- Modify: `telegram-bot/agent_runner.py`, `telegram-bot/bot.py`
- Test: `telegram-bot/tests/test_agent_runner_lifeos.py`

**Interfaces:**
- Consumes: the lifeos server (`python -m lifeos_mcp.server`) and its env contract (`LIFEOS_IDENTITY`, `LIFEOS_MAP_STORE`, `LIFEOS_BLOB_ACCOUNT_URL`, `LIFEOS_MAP_CONTAINER`, tokens).
- Produces: `build_options(stderr=None, chat_id=None)` includes a `lifeos` stdio server whose env carries `LIFEOS_IDENTITY = str(chat_id)` when `chat_id` is given, and `"mcp__lifeos"` in `allowed_tools`; `run_agent(prompt, chat_id=None)` forwards `chat_id`.

- [ ] **Step 1: Install lifeos-mcp into the bot venv (prereq for the server to import)**

Command: `../telegram-bot/.venv/Scripts/python.exe -m pip install -e .` (run from `lifeos-mcp/`). Also add `-e ./lifeos-mcp` (or the package) to `telegram-bot/requirements.txt` so Docker/CI installs it.

- [ ] **Step 2: Write the failing test**

Create `telegram-bot/tests/test_agent_runner_lifeos.py`:

```python
import os
os.environ.setdefault("LIFEOS_MAP_STORE", "blob")
os.environ.setdefault("LIFEOS_BLOB_ACCOUNT_URL", "https://acct.blob.core.windows.net")
from agent_runner import build_options

def test_lifeos_registered_with_identity():
    opts = build_options(chat_id=1672283963)
    servers = opts.mcp_servers
    assert "lifeos" in servers
    assert servers["lifeos"]["env"]["LIFEOS_IDENTITY"] == "1672283963"
    assert "mcp__lifeos" in opts.allowed_tools

def test_lifeos_present_without_chat_id():
    opts = build_options()
    assert "lifeos" in opts.mcp_servers  # still registered; identity empty
```

- [ ] **Step 3: Run to verify failure**

Run (from `telegram-bot/`): `.venv/Scripts/python.exe -m pytest tests/test_agent_runner_lifeos.py -q`
Expected: FAIL — `build_options()` has no `chat_id`; no `lifeos` server.

- [ ] **Step 4: Register lifeos in `build_options` and thread `chat_id`**

In `telegram-bot/agent_runner.py`, change the signature to
`def build_options(stderr=None, chat_id=None) -> ClaudeAgentOptions:` and, after the
`google-calendar` block, add:

```python
    # lifeos — our own MCP: deterministic get_today/get_week/add_record/create_event over
    # the map. Registered PROGRAMMATICALLY (project .mcp.json is skipped in headless runs).
    lifeos_env = {
        "NOTION_TOKEN": NOTION_TOKEN,
        "GOOGLE_OAUTH_CREDENTIALS": GOOGLE_OAUTH_CREDENTIALS,
        "GOOGLE_CALENDAR_MCP_TOKEN_PATH": GOOGLE_CALENDAR_MCP_TOKEN_PATH,
        "LIFEOS_MAP_STORE": os.environ.get("LIFEOS_MAP_STORE", "file"),
        "LIFEOS_BLOB_ACCOUNT_URL": os.environ.get("LIFEOS_BLOB_ACCOUNT_URL", ""),
        "LIFEOS_MAP_CONTAINER": os.environ.get("LIFEOS_MAP_CONTAINER", "maps"),
        "LIFEOS_IDENTITY": str(chat_id) if chat_id is not None else "",
    }
    mcp_servers["lifeos"] = {
        "type": "stdio", "command": sys.executable,
        "args": ["-m", "lifeos_mcp.server"], "env": lifeos_env,
    }
```

Add `"mcp__lifeos"` to the `allowed_tools` list.

- [ ] **Step 5: Forward `chat_id` from `run_agent` and `bot.py`**

In `agent_runner.py`, change `run_agent` to `async def run_agent(prompt: str, chat_id: int | None = None)` and pass `chat_id` into `build_options(stderr=stderr_chunks.append, chat_id=chat_id)`. In `telegram-bot/bot.py`, update the two `run_agent(route.command_text or text)` calls (lines ~114, ~120) to `run_agent(route.command_text or text, chat_id=chat_id)`.

- [ ] **Step 6: Run the test to verify it passes**

Run: `.venv/Scripts/python.exe -m pytest tests/test_agent_runner_lifeos.py -q`
Expected: PASS (2 tests). Also run the bot's existing tests: `.venv/Scripts/python.exe -m pytest -q`.

- [ ] **Step 7: Commit**

```bash
git add telegram-bot/agent_runner.py telegram-bot/bot.py \
        telegram-bot/tests/test_agent_runner_lifeos.py telegram-bot/requirements.txt
git commit -m "feat(bot): register lifeos MCP programmatically + thread chat id as LIFEOS_IDENTITY

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Out of scope (this plan)

- Rewriting `/refresh-notion` to the new shape, thinning `/today` `/week` `/add` onto the
  tools, and live validation against the real Notion — **Plan 2** (`docs/superpowers/plans/…-phase-b-cutover.md`).
- The multi-turn `LiveAgentClient`/`SESSION_MANAGER` path threading `chat_id` into its
  `options_factory` — small follow-up once the one-shot path is validated.
- ETag optimistic concurrency on blob writes (single-user; deferred).

## Self-review notes

- **Spec coverage:** persistence abstraction → Tasks 1–3; server per-identity load/save +
  `no_map` → Task 4; map lifecycle into blob → Task 5 (`mapctl`); infra account/container/role
  + output → Task 6; programmatic registration + `LIFEOS_IDENTITY` threading + deps → Task 7.
  refresh-notion/skills/live-validation are explicitly Plan 2.
- **Type consistency:** `MapStore.load/save(identity)`, `build_store(settings)`,
  `Settings.identity/map_store/map_dir/blob_account_url/map_container`, `MapNotFound`, and the
  `LIFEOS_*` env names are used identically across Tasks 1–7.
- **Green boundaries:** Tasks 1–5 keep the lifeos suite green; Task 4 updates the one server
  test that referenced the old `map_path`. Task 7 touches only the bot package.
