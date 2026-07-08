import os
import asyncio
os.environ.setdefault("LIFEOS_MAP_STORE", "blob")
os.environ.setdefault("LIFEOS_BLOB_ACCOUNT_URL", "https://acct.blob.core.windows.net")
from agent_runner import LiveAgentClient, build_options


def test_live_client_threads_identity_into_options():
    captured = {}

    def fake_factory(stderr=None, chat_id=None):
        captured["chat_id"] = chat_id
        return object()

    class FakeClient:
        def __init__(self, options):
            self.options = options

        async def connect(self):
            pass

    client = LiveAgentClient(options_factory=fake_factory, client_cls=FakeClient,
                             chat_id=1672283963)
    asyncio.run(client.connect())
    assert captured["chat_id"] == 1672283963


def test_build_options_carries_identity():
    opts = build_options(chat_id=1672283963)
    assert opts.mcp_servers["lifeos"]["env"]["LIFEOS_IDENTITY"] == "1672283963"


def test_lifeos_env_carries_azure_sp_creds_when_present(monkeypatch):
    # Local/dev blob testing: a service principal in the parent env must reach the
    # spawned lifeos server (its env is an explicit dict, not the full inherited env).
    monkeypatch.setenv("AZURE_CLIENT_ID", "cid")
    monkeypatch.setenv("AZURE_TENANT_ID", "tid")
    monkeypatch.setenv("AZURE_CLIENT_SECRET", "sekret")
    env = build_options(chat_id=1672283963).mcp_servers["lifeos"]["env"]
    assert env["AZURE_CLIENT_ID"] == "cid"
    assert env["AZURE_TENANT_ID"] == "tid"
    assert env["AZURE_CLIENT_SECRET"] == "sekret"


def test_lifeos_env_carries_map_dir_when_set(monkeypatch):
    # Container: lifeos-mcp is installed non-editable, so its default map dir resolves into
    # site-packages. The bot must thread an explicit LIFEOS_MAP_DIR to the spawned server.
    monkeypatch.setenv("LIFEOS_MAP_DIR", "/app/context/maps")
    env = build_options(chat_id=1672283963).mcp_servers["lifeos"]["env"]
    assert env["LIFEOS_MAP_DIR"] == "/app/context/maps"


def test_lifeos_env_omits_map_dir_when_unset(monkeypatch):
    # Local `python bot.py` (editable install) — let the server use its own default.
    monkeypatch.delenv("LIFEOS_MAP_DIR", raising=False)
    env = build_options(chat_id=1672283963).mcp_servers["lifeos"]["env"]
    assert "LIFEOS_MAP_DIR" not in env


def test_lifeos_env_omits_azure_sp_creds_when_absent(monkeypatch):
    # On the VM these are unset (managed identity via IMDS) — don't inject empty creds
    # that would make EnvironmentCredential misfire.
    for k in ("AZURE_CLIENT_ID", "AZURE_TENANT_ID", "AZURE_CLIENT_SECRET"):
        monkeypatch.delenv(k, raising=False)
    env = build_options(chat_id=1672283963).mcp_servers["lifeos"]["env"]
    assert "AZURE_CLIENT_ID" not in env
    assert "AZURE_TENANT_ID" not in env
    assert "AZURE_CLIENT_SECRET" not in env
