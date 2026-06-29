from dataclasses import dataclass, field
from datetime import date
from typing import Any

def _iso(d: date | None) -> str | None:
    return d.isoformat() if d else None

@dataclass
class KeyDate:
    label: str; date: date
    def to_dict(self) -> dict:
        return {"label": self.label, "date": _iso(self.date)}

@dataclass
class Record:
    id: str; role: str; title: str
    due_date: date | None; overdue: bool
    area_label: str; source_id: str
    key_dates: list = field(default_factory=list)
    fields: dict = field(default_factory=dict)
    source_label: str | None = None
    url: str | None = None
    def to_dict(self) -> dict:
        return {"id": self.id, "role": self.role, "title": self.title,
                "due_date": _iso(self.due_date), "overdue": self.overdue,
                "area_label": self.area_label, "source_id": self.source_id,
                "key_dates": [k.to_dict() for k in self.key_dates],
                "fields": self.fields, "source_label": self.source_label,
                "url": self.url}

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
    label: str; emoji: str; tasks: list
    key_dates: list; shift: ScheduleRecord | None
    def to_dict(self) -> dict:
        return {"label": self.label, "emoji": self.emoji,
                "tasks": [t.to_dict() for t in self.tasks],
                "key_dates": self.key_dates,
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
