from ..resolver_areas import resolve_sources, resolve_named
from ..resolver_schema import schema_for, prop
from ..notion_client import build_props

def add_record(map, notion, role: str, fields: dict, area: str | None = None) -> dict:
    target = None
    if area:
        # try a named group child first, then an anchored source whose area matches
        for akey, a in map.get("areas", {}).items():
            if area.lower() in a.get("label", "").lower() and "group" in a:
                target = resolve_named(map, notion, akey, area) or resolve_named(map, notion, akey, a["label"])
                break
        if target is None:
            named = None
            for akey in map.get("areas", {}):
                named = resolve_named(map, notion, akey, area)
                if named: break
            target = named
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
            "destination": target.area_label}
