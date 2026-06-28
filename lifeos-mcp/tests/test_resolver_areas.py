# tests/test_resolver_areas.py
import copy
from lifeos_mcp.resolver_areas import resolve_sources, iter_areas, resolve_named
from lifeos_mcp.errors import NotionNotFound
from tests.fixtures.maps import FIXTURE_MAP
from tests.fakes import FakeNotionClient

def test_iter_areas_order_and_labels():
    areas = iter_areas(FIXTURE_MAP)
    assert [a["label"] for a in areas] == ["Business", "University", "Work"]

def test_resolve_tasks_uses_cache_then_anchor():
    m = copy.deepcopy(FIXTURE_MAP)
    client = FakeNotionClient()  # no network needed; ventures already cached
    sources = resolve_sources(m, client, "tasks")
    ids = {s.source_id for s in sources}
    assert "uni-tasks" in ids                 # anchored university source
    assert "laundro-db" in ids                # cached venture tasks_db
    assert all(s.role == "tasks" for s in sources)

def test_resolve_tasks_enumerates_new_venture_and_writes_back():
    m = copy.deepcopy(FIXTURE_MAP)
    m["resolved"]["groups"]["ventures"] = {}   # force cache miss
    client = FakeNotionClient(
        children={"biz-root": [{"id": "van-page", "title": "Van Company"}]},
        child_db={"van-page": "van-db"},
    )
    sources = resolve_sources(m, client, "tasks")
    assert "van-db" in {s.source_id for s in sources}
    # write-back, keyed by ID, label stored
    assert m["resolved"]["groups"]["ventures"]["van-page"]["tasks_db"] == "van-db"
    assert m["resolved"]["groups"]["ventures"]["van-page"]["label"] == "Van Company"

def test_resolve_sets_source_label_for_venture_and_none_for_anchor():
    m = copy.deepcopy(FIXTURE_MAP)
    client = FakeNotionClient()  # ventures already cached, no network
    sources = resolve_sources(m, client, "tasks")
    by_id = {s.source_id: s for s in sources}
    assert by_id["laundro-db"].source_label == "Laundromat Hannover"
    assert by_id["laundro-db"].area_label == "Business"
    assert by_id["uni-tasks"].source_label is None
    assert by_id["uni-tasks"].area_label == "University"

def test_resolve_named_splits_area_and_source_label():
    m = copy.deepcopy(FIXTURE_MAP)
    named = resolve_named(m, FakeNotionClient(), "ventures", "Laundromat")
    assert named is not None
    assert named.source_id == "laundro-db"
    assert named.area_label == "Business"
    assert named.source_label == "Laundromat Hannover"
