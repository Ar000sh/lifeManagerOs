from lifeos_mcp.calendar_client import normalize_event

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
