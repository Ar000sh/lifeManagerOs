from datetime import date, datetime, time
from zoneinfo import ZoneInfo
from ..models import Record, KeyDate, ScheduleRecord, EventRecord, AreaBlock, TodayPayload
from ..resolver_areas import resolve_sources, iter_areas
from ..resolver_schema import col, is_complete, key_date_fields
from ..notion_client import extract_props
from ..resolver_stale import reconcile_due_groups, reconcile_group
from ..errors import NotionNotFound, WorkspaceUnavailable

def _to_date(s):
    return date.fromisoformat(s[:10]) if s else None

def _day_window(d: date, tz: str) -> tuple[str, str]:
    """RFC3339 start/end bounds for the local day in `tz`, so the calendar
    window matches the user's day rather than UTC."""
    zone = ZoneInfo(tz)
    return (datetime.combine(d, time.min, zone).isoformat(),
            datetime.combine(d, time.max, zone).isoformat())

def _task_rows(map, notion, source, today, warnings, stale_groups):
    tasks, key_dates = [], []
    try:
        rows = notion.query_data_source(source.source_id)
    except Exception as exc:
        warnings.append(f"task source {source.source_id} failed: {exc}")
        if isinstance(exc, NotionNotFound) and source.source_label:
            stale_groups.add(source.area_key)
        return tasks, key_dates
    sch = source.schema
    title_col, due_col = col(sch, "title"), col(sch, "due_date")
    kd_fields = key_date_fields(sch)
    for row in rows:
        props = extract_props(row)
        if is_complete(sch, props):
            continue
        rid = row.get("id", "")
        title = props.get(title_col) if title_col else None
        due = _to_date(props.get(due_col)) if due_col else None
        if not title:
            warnings.append(f"task {rid} missing required title")
        if due_col and not due:
            warnings.append(f"task {rid} missing required due_date")
        rec_fields = {}
        for k, d in sch.get("fields", {}).items():
            v = props.get(d["col"])
            if v is not None:
                rec_fields[k] = v
        rec_key_dates = []
        for k, d in kd_fields:
            kv = _to_date(props.get(d["col"]))
            if kv and kv >= today:   # only surface upcoming key dates, not past noise
                rec_key_dates.append(KeyDate(label=d["col"], date=kv))
                key_dates.append({"title": title or "", "label": d["col"],
                                  "date": kv.isoformat()})
        rec = Record(id=rid, role="tasks", title=title or "", due_date=due,
                     overdue=bool(due and due < today), area_label=source.area_label,
                     source_id=source.source_id, key_dates=rec_key_dates,
                     fields=rec_fields, source_label=source.source_label,
                     url=row.get("url"))
        if due and due <= today:
            tasks.append(rec)
    return tasks, key_dates

def _shift(map, notion, source, today, warnings):
    try:
        rows = notion.query_data_source(source.source_id)
    except Exception as exc:
        warnings.append(f"schedule source {source.source_id} failed: {exc}")
        return None
    sch = source.schema
    for row in rows:
        props = extract_props(row)
        d = _to_date(props.get(col(sch, "date"))) if col(sch, "date") else None
        if d == today:
            return ScheduleRecord(id=row.get("id", ""),
                title=props.get(col(sch, "title")) or "", date=d,
                start=props.get(col(sch, "start")) if col(sch, "start") else None,
                end=props.get(col(sch, "end")) if col(sch, "end") else None,
                source_id=source.source_id)
    return None

def get_today(map, notion, calendar, today: date, tz: str = "Europe/Berlin") -> TodayPayload:
    warnings: list[str] = []
    reconcile_due_groups(map, notion, today, warnings)
    task_sources = resolve_sources(map, notion, "tasks", warnings)
    sched_sources = resolve_sources(map, notion, "schedule", warnings)
    stale_groups: set[str] = set()
    blocks = []
    for area in iter_areas(map):
        a_tasks, a_key_dates, a_shift = [], [], None
        for s in (s for s in task_sources if s.area_key == area["key"]):
            ts, kds = _task_rows(map, notion, s, today, warnings, stale_groups)
            a_tasks += ts; a_key_dates += kds
        for s in (s for s in sched_sources if s.area_key == area["key"]):
            a_shift = a_shift or _shift(map, notion, s, today, warnings)
        if a_tasks or a_key_dates or a_shift:
            blocks.append(AreaBlock(area["label"], area["emoji"], a_tasks, a_key_dates, a_shift))
    for area_key in stale_groups:
        try:
            reconcile_group(map, notion, area_key)
        except WorkspaceUnavailable:
            raise
        except Exception as exc:
            warnings.append(f"reconcile {area_key} failed: {exc}")
    events = []
    try:
        tmin, tmax = _day_window(today, tz)
        events = [EventRecord(**e) for e in calendar.list_events(tmin, tmax)]
    except Exception as exc:
        warnings.append(f"calendar failed: {exc}")
    return TodayPayload(date=today, areas=blocks, events=events, warnings=warnings)
