import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping

_DEFAULT_MAP = Path(__file__).resolve().parent.parent.parent / "context" / "lifeos.map.json"

def load_map(path: str | Path) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))

def save_map(data: dict, path: str | Path) -> None:
    Path(path).write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")

@dataclass
class Settings:
    map_path: Path
    notion_token: str
    google_credentials: str
    google_token_path: str
    tz: str = "Europe/Berlin"

def load_settings(env: Mapping[str, str] | None = None) -> Settings:
    env = env if env is not None else os.environ
    return Settings(
        map_path=Path(env.get("LIFEOS_MAP_PATH", str(_DEFAULT_MAP))),
        notion_token=env.get("NOTION_TOKEN", "").strip(),
        google_credentials=env.get("GOOGLE_OAUTH_CREDENTIALS", "").strip(),
        google_token_path=env.get("GOOGLE_CALENDAR_MCP_TOKEN_PATH", "").strip(),
    )
