# tests/test_resolver_stale.py
import copy, pytest
from lifeos_mcp.resolver_stale import classify_error, reconcile_group
from lifeos_mcp.errors import NotionNotFound, NotionAuthError, TransientError, WorkspaceUnavailable
from tests.fixtures.maps import FIXTURE_MAP
from tests.fakes import FakeNotionClient

def test_classify():
    assert classify_error(TransientError("x")) == "transient"
    assert classify_error(NotionAuthError("x")) == "auth"
    assert classify_error(NotionNotFound("x")) == "notfound"

def test_rename_updates_label_not_membership():
    m = copy.deepcopy(FIXTURE_MAP)  # has venture laundro-page -> laundro-db
    client = FakeNotionClient(
        children={"biz-root": [{"id": "laundro-page", "title": "Laundromat Hannover GmbH"}]},
        child_db={"laundro-page": "laundro-db"},
    )
    summary = reconcile_group(m, client, "ventures")
    assert m["resolved"]["groups"]["ventures"]["laundro-page"]["label"] == "Laundromat Hannover GmbH"
    assert "laundro-page" in summary["renamed"]

def test_deleted_child_is_tombstoned():
    m = copy.deepcopy(FIXTURE_MAP)
    client = FakeNotionClient(children={"biz-root": []},
                              fail_with={"laundro-page": NotionNotFound})
    summary = reconcile_group(m, client, "ventures")
    assert "laundro-page" not in m["resolved"]["groups"]["ventures"]
    assert "laundro-page" in m["resolved"]["tombstones"]

def test_blast_radius_guard_raises_and_preserves_cache():
    m = copy.deepcopy(FIXTURE_MAP)
    m["resolved"]["groups"]["ventures"]["second-page"] = {
        "label": "Two", "role": "tasks", "tasks_db": "two-db", "cached_at": "2026-06-26"}
    client = FakeNotionClient(children={"biz-root": []},
        fail_with={"laundro-page": NotionAuthError, "second-page": NotionAuthError})
    before = copy.deepcopy(m["resolved"]["groups"]["ventures"])
    with pytest.raises(WorkspaceUnavailable):
        reconcile_group(m, client, "ventures")
    assert m["resolved"]["groups"]["ventures"] == before  # unchanged (rule iii)

def test_blast_radius_guard_preserves_moved_out_entry():
    import copy
    m = copy.deepcopy(FIXTURE_MAP)  # has venture laundro-page -> laundro-db
    # add two more cached children that will hard-fail
    m["resolved"]["groups"]["ventures"]["b-page"] = {
        "label": "B", "role": "tasks", "tasks_db": "b-db", "cached_at": "2026-06-26"}
    m["resolved"]["groups"]["ventures"]["c-page"] = {
        "label": "C", "role": "tasks", "tasks_db": "c-db", "cached_at": "2026-06-26"}
    # none present under the group; laundro-page retrieves OK (moved out),
    # b-page and c-page raise auth (2 hard failures)
    client = FakeNotionClient(
        children={"biz-root": []},
        pages={"laundro-page": {"id": "laundro-page"}},   # retrieve succeeds
        fail_with={"b-page": NotionAuthError, "c-page": NotionAuthError},
    )
    before = copy.deepcopy(m["resolved"]["groups"]["ventures"])
    with pytest.raises(WorkspaceUnavailable):
        reconcile_group(m, client, "ventures")
    assert m["resolved"]["groups"]["ventures"] == before  # NO mutation, incl. the moved-out entry

def test_drop_stale_removes_entry_by_tasks_db():
    import copy
    from lifeos_mcp.resolver_stale import drop_stale
    m = copy.deepcopy(FIXTURE_MAP)
    drop_stale(m, "laundro-db")
    assert "laundro-page" not in m["resolved"]["groups"]["ventures"]
