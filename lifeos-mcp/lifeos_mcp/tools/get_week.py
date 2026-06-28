from datetime import date, timedelta
from ..models import EventRecord, WeekPayload
from ..resolver_areas import resolve_sources
from ..resolver_schema import prop, is_done
from ..notion_client import extract_props
from .get_today import _to_date, _day_window

def week_bounds(today: date) -> tuple[date, date]:
    start = today - timedelta(days=today.weekday())  # Monday
    return start, start + timedelta(days=6)

def get_week(map, notion, calendar, today: date, tz: str = "Europe/Berlin") -> WeekPayload:
    start, end = week_bounds(today)
    warnings: list[str] = []
    buckets: dict[str, dict] = {}
    def bucket(d): return buckets.setdefault(d.isoformat(),
        {"date": d.isoformat(), "tasks": [], "exams": [], "shift": None, "events": []})

    for s in resolve_sources(map, notion, "tasks"):
        try:
            rows = notion.query_data_source(s.source_id)
        except Exception as exc:
            warnings.append(f"task source {s.source_id} failed: {exc}"); continue
        sch = s.schema
        tw = (sch.get("status_values") or {}).get("this_week")
        for row in rows:
            props = extract_props(row)
            if is_done(sch, props): continue
            due = _to_date(props.get(prop(sch,"due_date"))) if prop(sch,"due_date") else None
            exam = _to_date(props.get(prop(sch,"exam_date"))) if prop(sch,"exam_date") else None
            title = props.get(prop(sch,"title")) or ""
            status = props.get(prop(sch,"status")) if prop(sch,"status") else None
            item = {"title": title, "area": s.area_label, "status": status,
                    "due_date": due.isoformat() if due else None}
            if exam and start <= exam <= end: bucket(exam)["exams"].append(item)
            if due and start <= due <= end: bucket(due)["tasks"].append(item)
            elif tw and status == tw: bucket(start)["tasks"].append(item)

    for s in resolve_sources(map, notion, "schedule"):
        try:
            rows = notion.query_data_source(s.source_id)
        except Exception as exc:
            warnings.append(f"schedule {s.source_id} failed: {exc}"); continue
        sch = s.schema
        for row in rows:
            props = extract_props(row)
            d = _to_date(props.get(prop(sch,"date"))) if prop(sch,"date") else None
            if d and start <= d <= end:
                bucket(d)["shift"] = {"title": props.get(prop(sch,"title")) or "",
                    "start": props.get(prop(sch,"start")) if prop(sch,"start") else None,
                    "end": props.get(prop(sch,"end")) if prop(sch,"end") else None}

    try:
        evs = calendar.list_events(_day_window(start, tz)[0], _day_window(end, tz)[1])
        for e in evs:
            d = _to_date(e["start"])
            if d: bucket(d)["events"].append(EventRecord(**e).to_dict())
    except Exception as exc:
        warnings.append(f"calendar failed: {exc}")

    days = [buckets[k] for k in sorted(buckets)]
    summary = {"tasks": sum(len(d["tasks"]) for d in days),
               "exams": sum(len(d["exams"]) for d in days),
               "shifts": sum(1 for d in days if d["shift"])}
    return WeekPayload(start=start, end=end, days=days, summary=summary, warnings=warnings)
