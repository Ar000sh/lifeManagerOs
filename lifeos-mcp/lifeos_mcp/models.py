from dataclasses import dataclass, field
from datetime import date
from typing import Any

def _iso(d: date | None) -> str | None:
    return d.isoformat() if d else None

@dataclass
class TaskRecord:
    id: str; title: str; status: str | None; priority: str | None
    due_date: date | None; exam_date: date | None; area_label: str
    source_id: str; overdue: bool; url: str | None; catalog: str | None = None
    def to_dict(self) -> dict:
        return {"id": self.id, "title": self.title, "status": self.status,
                "priority": self.priority, "due_date": _iso(self.due_date),
                "exam_date": _iso(self.exam_date), "area_label": self.area_label,
                "source_id": self.source_id, "overdue": self.overdue,
                "url": self.url, "catalog": self.catalog}

@dataclass
class ScheduleRecord:
    id: str; title: str; date: date | None; start: str | None; end: str | None; source_id: str
    def to_dict(self) -> dict:
        return {"id": self.id, "title": self.title, "date": _iso(self.date),
                "start": self.start, "end": self.end, "source_id": self.source_id}

@dataclass
class EventRecord:
    id: str; title: str; start: str; end: str
    def to_dict(self) -> dict:
        return {"id": self.id, "title": self.title, "start": self.start, "end": self.end}

@dataclass
class CatalogRecord:
    id: str; title: str; extra: dict = field(default_factory=dict)
    def to_dict(self) -> dict:
        return {"id": self.id, "title": self.title, **self.extra}

@dataclass
class AreaBlock:
    label: str; emoji: str; tasks: list[TaskRecord]
    exams: list[TaskRecord]; shift: ScheduleRecord | None
    def to_dict(self) -> dict:
        return {"label": self.label, "emoji": self.emoji,
                "tasks": [t.to_dict() for t in self.tasks],
                "exams": [e.to_dict() for e in self.exams],
                "shift": self.shift.to_dict() if self.shift else None}

@dataclass
class TodayPayload:
    date: date; areas: list[AreaBlock]; events: list[EventRecord]; warnings: list[str]
    def to_dict(self) -> dict:
        return {"date": _iso(self.date), "areas": [a.to_dict() for a in self.areas],
                "events": [e.to_dict() for e in self.events], "warnings": self.warnings}

@dataclass
class WeekPayload:
    start: date; end: date; days: list[dict]; summary: dict; warnings: list[str]
    def to_dict(self) -> dict:
        return {"start": _iso(self.start), "end": _iso(self.end),
                "days": self.days, "summary": self.summary, "warnings": self.warnings}
