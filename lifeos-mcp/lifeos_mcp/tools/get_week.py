from datetime import date, timedelta
from ..models import EventRecord, WeekPayload
from ..resolver_areas import resolve_sources
from ..resolver_schema import col, is_complete, week_match, key_date_fields
from ..notion_client import extract_props
from ..resolver_stale import reconcile_due_groups, reconcile_group
from ..errors import NotionNotFound, WorkspaceUnavailable
from .get_today import _to_date, _day_window

def week_bounds(today: date) -> tuple[date, date]:
    start = today - timedelta(days=today.weekday())  # Monday
    return start, start + timedelta(days=6)

def get_week(map, notion, calendar, today: date, tz: str = "Europe/Berlin") -> WeekPayload:
    start, end = week_bounds(today)
    warnings: list[str] = []
    reconcile_due_groups(map, notion, today, warnings)
    buckets: dict[str, dict] = {}
    def bucket(d): return buckets.setdefault(d.isoformat(),
        {"date": d.isoformat(), "tasks": [], "key_dates": [], "shift": None, "events": []})

    stale_groups: set[str] = set()
    for s in resolve_sources(map, notion, "tasks", warnings):
        try:
            rows = notion.query_data_source(s.source_id)
        except Exception as exc:
            warnings.append(f"task source {s.source_id} failed: {exc}")
            if isinstance(exc, NotionNotFound) and s.source_label:
                stale_groups.add(s.area_key)
            continue
        sch = s.schema
        title_col, due_col, status_col = col(sch, "title"), col(sch, "due_date"), col(sch, "status")
        kd_fields = key_date_fields(sch)
        for row in rows:
            props = extract_props(row)
            if is_complete(sch, props):
                continue
            due = _to_date(props.get(due_col)) if due_col else None
            title = props.get(title_col) or ""
            status = props.get(status_col) if status_col else None
            item = {"title": title, "area": s.area_label, "source_label": s.source_label,
                    "status": status, "due_date": due.isoformat() if due else None}
            for k, d in kd_fields:
                kv = _to_date(props.get(d["col"]))
                if kv and start <= kv <= end:
                    bucket(kv)["key_dates"].append({**item, "label": d["col"],
                                                    "date": kv.isoformat()})
            if due and start <= due <= end:
                bucket(due)["tasks"].append(item)
            elif week_match(sch, props):
                bucket(start)["tasks"].append(item)

    for s in resolve_sources(map, notion, "schedule", warnings):
        try:
            rows = notion.query_data_source(s.source_id)
        except Exception as exc:
            warnings.append(f"schedule {s.source_id} failed: {exc}"); continue
        sch = s.schema
        for row in rows:
            props = extract_props(row)
            d = _to_date(props.get(col(sch, "date"))) if col(sch, "date") else None
            if d and start <= d <= end:
                bucket(d)["shift"] = {"title": props.get(col(sch, "title")) or "",
                    "start": props.get(col(sch, "start")) if col(sch, "start") else None,
                    "end": props.get(col(sch, "end")) if col(sch, "end") else None}

    for area_key in stale_groups:
        try:
            reconcile_group(map, notion, area_key)
        except WorkspaceUnavailable:
            raise
        except Exception as exc:
            warnings.append(f"reconcile {area_key} failed: {exc}")

    try:
        evs = calendar.list_events(_day_window(start, tz)[0], _day_window(end, tz)[1])
        for e in evs:
            d = _to_date(e["start"])
            if d: bucket(d)["events"].append(EventRecord(**e).to_dict())
    except Exception as exc:
        warnings.append(f"calendar failed: {exc}")

    days = [buckets[k] for k in sorted(buckets)]
    summary = {"tasks": sum(len(d["tasks"]) for d in days),
               "key_dates": sum(len(d["key_dates"]) for d in days),
               "shifts": sum(1 for d in days if d["shift"])}
    return WeekPayload(start=start, end=end, days=days, summary=summary, warnings=warnings)
