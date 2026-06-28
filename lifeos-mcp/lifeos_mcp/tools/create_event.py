from datetime import datetime, timedelta

def create_event(calendar, title: str, start: str, end: str | None = None,
                 notes: str | None = None, default_minutes: int = 60) -> dict:
    if not end:
        dt = datetime.fromisoformat(start)
        end = (dt + timedelta(minutes=default_minutes)).isoformat()
    ev = calendar.create_event(title, start, end, notes)
    return {"created": True, "id": ev.get("id"), "link": ev.get("htmlLink")}
