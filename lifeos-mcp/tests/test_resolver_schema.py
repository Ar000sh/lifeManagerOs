from lifeos_mcp.resolver_schema import schema_for, prop, is_done
from tests.fixtures.maps import LEGACY_FIXTURE_MAP as FIXTURE_MAP, LEGACY_ALT_MAP as ALT_MAP

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

from tests.fixtures.maps import FIXTURE_MAP as NEW_FIXTURE_MAP, ALT_MAP as NEW_ALT_MAP
from lifeos_mcp.resolver_schema import (
    field_def, col, required_core, is_complete, week_match, key_date_fields)

def test_col_core_and_dynamic():
    sch = NEW_FIXTURE_MAP["role_schemas"]["university_tasks_db"]
    assert col(sch, "due_date") == "Due Date"          # core
    assert col(sch, "exam_date") == "Exam Date"        # dynamic
    assert col(sch, "nope") is None

def test_required_core_is_title_and_due_date():
    sch = NEW_FIXTURE_MAP["role_schemas"]["university_tasks_db"]
    assert required_core(sch) == ["title", "due_date"]

def test_is_complete_status_and_checkbox():
    uni = NEW_FIXTURE_MAP["role_schemas"]["university_tasks_db"]
    assert is_complete(uni, {"Status": "Done"}) is True
    assert is_complete(uni, {"Status": "Open"}) is False
    todo = NEW_ALT_MAP["role_schemas"]["todo_db"]
    assert is_complete(todo, {"Erledigt": True}) is True
    assert is_complete(todo, {"Erledigt": False}) is False

def test_week_match_uses_predicate():
    sch = NEW_FIXTURE_MAP["role_schemas"]["university_tasks_db"]
    assert week_match(sch, {"Status": "This Week"}) is True
    assert week_match(sch, {"Status": "Open"}) is False

def test_key_date_fields_only_highlighted_dates():
    sch = NEW_FIXTURE_MAP["role_schemas"]["university_tasks_db"]
    keys = [k for k, _ in key_date_fields(sch)]
    assert keys == ["exam_date"]
