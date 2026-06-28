from ..resolver_areas import resolve_sources
from ..resolver_schema import prop
from ..notion_client import build_props

def _label(s):
    return s.source_label or s.area_label

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
    if prop(sch, "priority") and "priority" not in fields:
        fields["priority"] = "Medium"
    props = build_props(sch, fields)
    page = notion.create_page(target.source_id, props)
    return {"created": True, "id": page.get("id"), "url": page.get("url"),
            "destination": _label(target)}
