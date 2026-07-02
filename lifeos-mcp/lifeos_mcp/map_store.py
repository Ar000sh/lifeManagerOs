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
