# tests/test_resolver_stale.py
import copy, pytest
from datetime import date
from lifeos_mcp.resolver_stale import classify_error, reconcile_group, reconcile_due_groups
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

def test_reconcile_due_runs_and_stamps_when_unstamped():
    m = copy.deepcopy(FIXTURE_MAP)
    client = FakeNotionClient(
        children={"biz-root": [{"id": "laundro-page", "title": "Laundromat HQ"}]},
        child_db={"laundro-page": "laundro-db"})
    reconcile_due_groups(m, client, date(2026, 6, 29))
    assert m["resolved"]["groups"]["ventures"]["laundro-page"]["label"] == "Laundromat HQ"
    assert m["resolved"]["reconciled"]["ventures"] == "2026-06-29"

def test_reconcile_due_skips_when_stamped_today():
    m = copy.deepcopy(FIXTURE_MAP)
    m.setdefault("resolved", {}).setdefault("reconciled", {})["ventures"] = "2026-06-29"
    client = FakeNotionClient(
        children={"biz-root": [{"id": "laundro-page", "title": "Renamed"}]},
        child_db={"laundro-page": "laundro-db"})
    reconcile_due_groups(m, client, date(2026, 6, 29))
    # gate held -> no rename applied
    assert m["resolved"]["groups"]["ventures"]["laundro-page"]["label"] == "Laundromat Hannover"

def test_reconcile_due_skips_empty_group_cache():
    m = copy.deepcopy(FIXTURE_MAP)
    m["resolved"]["groups"]["ventures"] = {}   # undiscovered
    calls = {"n": 0}
    class C(FakeNotionClient):
        def get_block_children(self, b):
            calls["n"] += 1
            return []
    reconcile_due_groups(m, C(), date(2026, 6, 29))
    assert calls["n"] == 0

def test_reconcile_due_propagates_workspace_unavailable():
    m = copy.deepcopy(FIXTURE_MAP)
    m["resolved"]["groups"]["ventures"]["second-page"] = {
        "label": "Two", "role": "tasks", "tasks_db": "two-db", "cached_at": "2026-06-26"}
    client = FakeNotionClient(children={"biz-root": []},
        fail_with={"laundro-page": NotionAuthError, "second-page": NotionAuthError})
    with pytest.raises(WorkspaceUnavailable):
        reconcile_due_groups(m, client, date(2026, 6, 29))

def test_reconcile_due_transient_warns_and_does_not_stamp():
    m = copy.deepcopy(FIXTURE_MAP)
    client = FakeNotionClient(fail_with={"biz-root": TransientError})
    warnings = []
    reconcile_due_groups(m, client, date(2026, 6, 29), warnings)
    assert any("reconcile" in w and "ventures" in w for w in warnings)
    assert "ventures" not in m["resolved"].get("reconciled", {})
