import json
from lifeos_mcp.calendar_client import normalize_event, load_authorized_user_info

def test_normalize_timed_event():
    raw = {"id": "e1", "summary": "Lecture",
           "start": {"dateTime": "2026-06-27T10:00:00+02:00"},
           "end": {"dateTime": "2026-06-27T12:00:00+02:00"}}
    assert normalize_event(raw) == {"id": "e1", "title": "Lecture",
        "start": "2026-06-27T10:00:00+02:00", "end": "2026-06-27T12:00:00+02:00"}

def test_normalize_all_day_event():
    raw = {"id": "e2", "summary": "Holiday",
           "start": {"date": "2026-06-27"}, "end": {"date": "2026-06-28"}}
    assert normalize_event(raw)["start"] == "2026-06-27"

def _write(path, data):
    path.write_text(json.dumps(data), encoding="utf-8")

def test_load_cocal_token_merges_client_secrets(tmp_path):
    # @cocal/google-calendar-mcp token file: creds nested under "normal",
    # no client_id/client_secret (those live in the OAuth keys file).
    token = tmp_path / "tokens"
    _write(token, {"normal": {"access_token": "at", "refresh_token": "rt",
                              "scope": "https://www.googleapis.com/auth/calendar",
                              "token_type": "Bearer", "expiry_date": 1751500000000}})
    keys = tmp_path / "gcp-oauth.keys.json"
    _write(keys, {"installed": {"client_id": "cid", "client_secret": "cs"}})
    info = load_authorized_user_info(str(token), str(keys))
    assert info == {"type": "authorized_user", "client_id": "cid",
                    "client_secret": "cs", "refresh_token": "rt"}

def test_load_native_authorized_user_token_passes_through(tmp_path):
    token = tmp_path / "token.json"
    native = {"type": "authorized_user", "client_id": "cid",
              "client_secret": "cs", "refresh_token": "rt"}
    _write(token, native)
    info = load_authorized_user_info(str(token), str(tmp_path / "missing-keys.json"))
    assert info == native
