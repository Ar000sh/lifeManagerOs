from datetime import date
from lifeos_mcp.models import TaskRecord, TodayPayload, AreaBlock

def test_task_to_dict_serializes_date():
    t = TaskRecord(id="1", title="Pay rent", status="Open", priority="High",
                   due_date=date(2026, 6, 27), exam_date=None, area_label="Business",
                   source_id="db1", overdue=True, url="http://n/1")
    d = t.to_dict()
    assert d["due_date"] == "2026-06-27"
    assert d["overdue"] is True

def test_today_payload_to_dict_nested():
    p = TodayPayload(date=date(2026, 6, 27),
                     areas=[AreaBlock(label="Work", emoji="💼", tasks=[], key_dates=[], shift=None)],
                     events=[], warnings=[])
    d = p.to_dict()
    assert d["date"] == "2026-06-27"
    assert d["areas"][0]["label"] == "Work"

def test_record_to_dict_with_key_dates_and_fields():
    from lifeos_mcp.models import Record, KeyDate
    from datetime import date
    r = Record(id="1", role="tasks", title="Essay", due_date=date(2026, 6, 27),
               overdue=False, area_label="University", source_id="uni-tasks",
               key_dates=[KeyDate(label="Exam Date", date=date(2026, 7, 10))],
               fields={"priority": "High"}, source_label=None, url="http://n/1")
    d = r.to_dict()
    assert d["title"] == "Essay"
    assert d["due_date"] == "2026-06-27"
    assert d["key_dates"] == [{"label": "Exam Date", "date": "2026-07-10"}]
    assert d["fields"] == {"priority": "High"}
