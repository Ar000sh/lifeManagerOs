from tests.fixtures.maps import FIXTURE_MAP, ALT_MAP
from lifeos_mcp.resolver_schema import (
    field_def, col, required_core, is_complete, week_match, key_date_fields)

def test_col_core_and_dynamic():
    sch = FIXTURE_MAP["role_schemas"]["university_tasks_db"]
    assert col(sch, "due_date") == "Due Date"          # core
    assert col(sch, "exam_date") == "Exam Date"        # dynamic
    assert col(sch, "nope") is None

def test_required_core_is_title_and_due_date():
    sch = FIXTURE_MAP["role_schemas"]["university_tasks_db"]
    assert required_core(sch) == ["title", "due_date"]

def test_is_complete_status_and_checkbox():
    uni = FIXTURE_MAP["role_schemas"]["university_tasks_db"]
    assert is_complete(uni, {"Status": "Done"}) is True
    assert is_complete(uni, {"Status": "Open"}) is False
    todo = ALT_MAP["role_schemas"]["todo_db"]
    assert is_complete(todo, {"Erledigt": True}) is True
    assert is_complete(todo, {"Erledigt": False}) is False

def test_week_match_uses_predicate():
    sch = FIXTURE_MAP["role_schemas"]["university_tasks_db"]
    assert week_match(sch, {"Status": "This Week"}) is True
    assert week_match(sch, {"Status": "Open"}) is False

def test_key_date_fields_only_highlighted_dates():
    sch = FIXTURE_MAP["role_schemas"]["university_tasks_db"]
    keys = [k for k, _ in key_date_fields(sch)]
    assert keys == ["exam_date"]
