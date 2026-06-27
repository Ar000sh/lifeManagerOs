def schema_for(map: dict, source_id: str, role: str) -> dict:
    schemas = map.get("role_schemas", {})
    if source_id in schemas:
        return schemas[source_id]
    return map.get("child_schema_defaults", {}).get(role, {})

def prop(schema: dict, prop_role: str) -> str | None:
    return schema.get(prop_role)  # rule D: absent -> None

def is_done(schema: dict, props: dict) -> bool:
    done_when = schema.get("done_when")
    if done_when:  # rule C: checkbox predicate
        return props.get(done_when["property"]) == done_when.get("equals", True)
    status_col = schema.get("status")
    done_val = (schema.get("status_values") or {}).get("done")
    if status_col and done_val is not None:
        return props.get(status_col) == done_val
    return False
