from datetime import date
from ..resolver_areas import resolve_sources
from ..resolver_schema import prop, is_done
from ..notion_client import extract_props
from .get_today import _to_date

def query_records(map, notion, role: str, filters: dict | None = None) -> list[dict]:
    filters = filters or {}
    out = []
    for s in resolve_sources(map, notion, role):
        if filters.get("area"):
            hay = [s.area_label] + ([s.source_label] if s.source_label else [])
            if not any(filters["area"].lower() in h.lower() for h in hay):
                continue
        sch = s.schema
        try:
            rows = notion.query_data_source(s.source_id)
        except Exception:
            continue
        for row in rows:
            props = extract_props(row)
            status = props.get(prop(sch, "status")) if prop(sch, "status") else None
            due = _to_date(props.get(prop(sch, "due_date"))) if prop(sch, "due_date") else None
            if filters.get("not_done") and is_done(sch, props): continue
            if filters.get("status") and status != filters["status"]: continue
            if filters.get("due_before") and not (due and due < date.fromisoformat(filters["due_before"])): continue
            if filters.get("due_after") and not (due and due > date.fromisoformat(filters["due_after"])): continue
            out.append({"id": row.get("id",""), "title": props.get(prop(sch,"title")) or "",
                        "status": status, "due_date": due.isoformat() if due else None,
                        "area": s.area_label, "source_label": s.source_label,
                        "source_id": s.source_id, "url": row.get("url")})
    return out
