def schema_for(map: dict, source_id: str, role: str) -> dict:
    schemas = map.get("role_schemas", {})
    if source_id in schemas:
        return schemas[source_id]
    return map.get("child_schema_defaults", {}).get(role, {})

CORE_KEYS = {"tasks": ("title", "due_date"),
             "schedule": ("title", "date", "start", "end"),
             "catalog": ("title",)}
REQUIRED = {"tasks": ("title", "due_date"),
            "schedule": ("title", "date"),
            "catalog": ("title",)}

def field_def(schema: dict, key: str) -> dict | None:
    top = schema.get(key)
    if isinstance(top, dict) and "col" in top:
        return top
    return schema.get("fields", {}).get(key)

def col(schema: dict, key: str) -> str | None:
    d = field_def(schema, key)
    return d.get("col") if d else None

def required_core(schema: dict) -> list[str]:
    return [k for k in REQUIRED.get(schema.get("role"), ("title",)) if col(schema, k)]

def is_complete(schema: dict, props: dict) -> bool:
    p = schema.get("done_predicate")
    return bool(p) and props.get(p["col"]) == p.get("equals", True)

def week_match(schema: dict, props: dict) -> bool:
    p = schema.get("week_predicate")
    return bool(p) and props.get(p["col"]) == p.get("equals")

def key_date_fields(schema: dict) -> list[tuple[str, dict]]:
    return [(k, d) for k, d in schema.get("fields", {}).items()
            if d.get("type") == "date" and d.get("highlight")]
