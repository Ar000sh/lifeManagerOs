from ..resolver_areas import resolve_sources, resolve_named
from ..resolver_schema import prop
from ..notion_client import build_props

def add_record(map, notion, role: str, fields: dict, area: str | None = None) -> dict:
    target = None
    if area:
        # 1) match a group child by name (e.g. "Laundromat"), role-filtered
        for akey in map.get("areas", {}):
            named = resolve_named(map, notion, akey, area)
            if named and named.role == role:
                target = named
                break
        # 2) else match an area by its label (e.g. "University") among role sources
        if target is None:
            for s in resolve_sources(map, notion, role):
                if area.lower() in s.area_label.lower():
                    target = s
                    break
    if target is None:
        sources = resolve_sources(map, notion, role)
        if not sources:
            return {"created": False, "error": f"no source for role {role}"}
        target = sources[0]
    sch = target.schema
    fields = dict(fields)
    if prop(sch, "priority") and "priority" not in fields:
        fields["priority"] = "Medium"
    props = build_props(sch, fields)
    page = notion.create_page(target.source_id, props)
    return {"created": True, "id": page.get("id"), "url": page.get("url"),
            "destination": target.source_label or target.area_label}
