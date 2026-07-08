import json
from pathlib import Path
from typing import Protocol

class CalendarClient(Protocol):
    def list_events(self, time_min: str, time_max: str) -> list[dict]: ...
    def create_event(self, title: str, start: str, end: str, notes=None) -> dict: ...

def load_authorized_user_info(token_path: str, credentials_path: str) -> dict:
    data = json.loads(Path(token_path).read_text(encoding="utf-8"))
    if "normal" not in data:
        return data
    # @cocal/google-calendar-mcp token: creds nested under "normal", client
    # id/secret only in the OAuth keys file.
    keys = json.loads(Path(credentials_path).read_text(encoding="utf-8"))
    client = keys.get("installed") or keys.get("web") or {}
    return {"type": "authorized_user",
            "client_id": client["client_id"],
            "client_secret": client["client_secret"],
            "refresh_token": data["normal"]["refresh_token"]}

def normalize_event(raw: dict) -> dict:
    def _se(side): return side.get("dateTime") or side.get("date")
    return {"id": raw.get("id"), "title": raw.get("summary", ""),
            "start": _se(raw.get("start", {})), "end": _se(raw.get("end", {}))}

class GoogleCalendarClient:
    def __init__(self, credentials_path: str, token_path: str, tz: str = "Europe/Berlin"):
        from google.oauth2.credentials import Credentials
        from googleapiclient.discovery import build
        creds = Credentials.from_authorized_user_info(
            load_authorized_user_info(token_path, credentials_path),
            ["https://www.googleapis.com/auth/calendar"])
        self._svc = build("calendar", "v3", credentials=creds, cache_discovery=False)
        self._tz = tz

    def list_events(self, time_min: str, time_max: str) -> list[dict]:
        resp = self._svc.events().list(calendarId="primary", timeMin=time_min,
            timeMax=time_max, singleEvents=True, orderBy="startTime").execute()
        return [normalize_event(e) for e in resp.get("items", [])]

    def create_event(self, title: str, start: str, end: str, notes=None) -> dict:
        body = {"summary": title, "description": notes or "",
                "start": {"dateTime": start, "timeZone": self._tz},
                "end": {"dateTime": end, "timeZone": self._tz}}
        ev = self._svc.events().insert(calendarId="primary", body=body).execute()
        return {"id": ev["id"], "htmlLink": ev.get("htmlLink")}
