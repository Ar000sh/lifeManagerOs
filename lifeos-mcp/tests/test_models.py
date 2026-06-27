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
                     areas=[AreaBlock(label="Work", emoji="💼", tasks=[], exams=[], shift=None)],
                     events=[], warnings=[])
    d = p.to_dict()
    assert d["date"] == "2026-06-27"
    assert d["areas"][0]["label"] == "Work"
