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
