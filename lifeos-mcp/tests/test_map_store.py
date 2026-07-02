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


# Named to match Azure's real class: AzureBlobMapStore.load duck-types on
# type(exc).__name__ == "ResourceNotFoundError" (no azure import needed in tests).
class ResourceNotFoundError(Exception):
    pass

class _FakeBlob:
    def __init__(self, store, name):
        self._store, self._name = store, name
    def download_blob(self):
        if self._name not in self._store:
            raise ResourceNotFoundError(self._name)
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
