from lifeos_mcp.resolver_schema import schema_for, prop, is_done
from tests.fixtures.maps import FIXTURE_MAP, ALT_MAP

def test_prop_present_and_absent():
    sch = schema_for(FIXTURE_MAP, "university_tasks_db", "tasks")
    assert prop(sch, "due_date") == "Due Date"
    assert prop(sch, "nonexistent") is None          # rule D

def test_is_done_via_status_value():
    sch = schema_for(FIXTURE_MAP, "university_tasks_db", "tasks")
    assert is_done(sch, {"Status": "Done"}) is True
    assert is_done(sch, {"Status": "Open"}) is False

def test_is_done_via_checkbox_predicate():
    sch = schema_for(ALT_MAP, "todo_db", "tasks")     # rule C: done_when
    assert is_done(sch, {"Erledigt": True}) is True
    assert is_done(sch, {"Erledigt": False}) is False

def test_child_schema_default_used_when_source_absent():
    sch = schema_for(FIXTURE_MAP, "some-enumerated-child-db", "tasks")
    assert prop(sch, "title") == "Name"               # falls back to child_schema_defaults
