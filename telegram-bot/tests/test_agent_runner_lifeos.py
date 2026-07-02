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
