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
