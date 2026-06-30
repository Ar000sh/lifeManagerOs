from ..resolver_areas import resolve_sources
from ..resolver_schema import col, required_core
from ..notion_client import build_props

def _label(s):
    return s.source_label or s.area_label

def _blank(v):
    """A required value is missing if absent, None, or an empty/whitespace string."""
    return v is None or (isinstance(v, str) and not v.strip())

def add_record(map, notion, role: str, fields: dict, area: str | None = None) -> dict:
    sources = resolve_sources(map, notion, role)
    if not sources:
        return {"created": False, "error": f"no source for role {role}"}

    if area:
        a = area.lower()
        candidates = [s for s in sources
                      if (s.source_label and a in s.source_label.lower())
                      or a in s.area_label.lower()]
        if not candidates:
            return {"created": False, "error": "destination_not_found",
                    "candidates": sorted({_label(s) for s in sources})}
    else:
        candidates = sources

    if len(candidates) > 1:
        return {"created": False, "error": "ambiguous_destination",
                "candidates": sorted({_label(s) for s in candidates})}

    target = candidates[0]
    sch = target.schema
    fields = dict(fields)
    missing = [k for k in required_core(sch) if _blank(fields.get(k))]
    if missing:
        return {"created": False, "error": "missing_required", "fields": missing}
    if col(sch, "priority") and "priority" not in fields:
        fields["priority"] = "Medium"
    props = build_props(sch, fields)
    page = notion.create_page(target.source_id, props)
    return {"created": True, "id": page.get("id"), "url": page.get("url"),
            "destination": _label(target)}
