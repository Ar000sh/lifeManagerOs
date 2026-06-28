from datetime import date, datetime, time
from zoneinfo import ZoneInfo
from ..models import TaskRecord, ScheduleRecord, EventRecord, AreaBlock, TodayPayload
from ..resolver_areas import resolve_sources, iter_areas
from ..resolver_schema import prop, is_done
from ..notion_client import extract_props
from ..resolver_stale import reconcile_due_groups

def _to_date(s):
    return date.fromisoformat(s[:10]) if s else None

def _day_window(d: date, tz: str) -> tuple[str, str]:
    """RFC3339 start/end bounds for the local day in `tz`, so the calendar
    window matches the user's day rather than UTC."""
    zone = ZoneInfo(tz)
    return (datetime.combine(d, time.min, zone).isoformat(),
            datetime.combine(d, time.max, zone).isoformat())

def _task_rows(map, notion, source, today, warnings):
    tasks, exams = [], []
    try:
        rows = notion.query_data_source(source.source_id)
    except Exception as exc:
        warnings.append(f"task source {source.source_id} failed: {exc}")
        return tasks, exams
    sch = source.schema
    for row in rows:
        props = extract_props(row)
        if is_done(sch, props):
            continue
        due = _to_date(props.get(prop(sch, "due_date"))) if prop(sch, "due_date") else None
        exam = _to_date(props.get(prop(sch, "exam_date"))) if prop(sch, "exam_date") else None
        title = props.get(prop(sch, "title")) or ""
        rec = TaskRecord(id=row.get("id",""), title=title,
            status=props.get(prop(sch,"status")) if prop(sch,"status") else None,
            priority=props.get(prop(sch,"priority")) if prop(sch,"priority") else None,
            due_date=due, exam_date=exam, area_label=source.area_label,
            source_id=source.source_id, overdue=bool(due and due < today),
            url=row.get("url"), source_label=source.source_label)
        if exam:
            exams.append(rec)
        if due and due <= today:
            tasks.append(rec)
    return tasks, exams

def _shift(map, notion, source, today, warnings):
    try:
        rows = notion.query_data_source(source.source_id)
    except Exception as exc:
        warnings.append(f"schedule source {source.source_id} failed: {exc}")
        return None
    sch = source.schema
    for row in rows:
        props = extract_props(row)
        d = _to_date(props.get(prop(sch, "date"))) if prop(sch, "date") else None
        if d == today:
            return ScheduleRecord(id=row.get("id",""), title=props.get(prop(sch,"title")) or "",
                date=d, start=props.get(prop(sch,"start")) if prop(sch,"start") else None,
                end=props.get(prop(sch,"end")) if prop(sch,"end") else None,
                source_id=source.source_id)
    return None

def get_today(map, notion, calendar, today: date, tz: str = "Europe/Berlin") -> TodayPayload:
    warnings: list[str] = []
    reconcile_due_groups(map, notion, today, warnings)
    task_sources = resolve_sources(map, notion, "tasks", warnings)
    sched_sources = resolve_sources(map, notion, "schedule", warnings)
    blocks = []
    for area in iter_areas(map):
        a_tasks, a_exams, a_shift = [], [], None
        for s in (s for s in task_sources if s.area_key == area["key"]):
            ts, es = _task_rows(map, notion, s, today, warnings)
            a_tasks += ts; a_exams += es
        for s in (s for s in sched_sources if s.area_key == area["key"]):
            a_shift = a_shift or _shift(map, notion, s, today, warnings)
        if a_tasks or a_exams or a_shift:
            blocks.append(AreaBlock(area["label"], area["emoji"], a_tasks, a_exams, a_shift))
    events = []
    try:
        tmin, tmax = _day_window(today, tz)
        events = [EventRecord(**e) for e in calendar.list_events(tmin, tmax)]
    except Exception as exc:
        warnings.append(f"calendar failed: {exc}")
    return TodayPayload(date=today, areas=blocks, events=events, warnings=warnings)
