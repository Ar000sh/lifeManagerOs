from datetime import date
from .errors import NotionNotFound, NotionAuthError, TransientError, WorkspaceUnavailable

def classify_error(exc) -> str:
    if isinstance(exc, TransientError): return "transient"
    if isinstance(exc, NotionAuthError): return "auth"
    if isinstance(exc, NotionNotFound): return "notfound"
    return "transient"

def reconcile_group(map: dict, client, area_key: str) -> dict:
    cache = map["resolved"]["groups"].setdefault(area_key, {})
    group = map["areas"][area_key]["group"]
    summary = {"renamed": [], "dropped": [], "tombstoned": [], "added": []}

    # current children under the anchor, by id (resolve anchor name -> id)
    under = map.get("anchors", {}).get(group["under"], group["under"])
    present = {c["id"]: c for c in client.get_block_children(under)}

    deletions, move_outs, hard_failures = [], [], 0
    for cid, entry in list(cache.items()):
        if cid in present:
            new_label = present[cid].get("title", entry["label"])
            if new_label != entry["label"]:
                entry["label"] = new_label; summary["renamed"].append(cid)
            continue
        # not under the group anymore: is it deleted, or just moved/inaccessible?
        try:
            client.retrieve(cid)
            move_outs.append(cid); summary["dropped"].append(cid)  # moved out (deferred past guard)
        except Exception as exc:
            kind = classify_error(exc)
            if kind == "notfound":
                deletions.append(cid)
            else:
                hard_failures += 1

    # blast-radius guard (rules ii–iii): >1 hard failure => connection/permission
    if hard_failures > 1:
        raise WorkspaceUnavailable(f"{hard_failures} children failed to resolve in {area_key}")

    for cid in move_outs:
        cache.pop(cid, None)

    for cid in deletions:
        entry = cache.pop(cid)
        map["resolved"]["tombstones"][cid] = {
            "reason": "deleted", "label": entry.get("label"), "seen_at": date.today().isoformat()}
        summary["tombstoned"].append(cid)

    # add genuinely new children
    ignored = set(map["resolved"].get("ignored", []))
    for cid, child in present.items():
        if cid in cache or cid in map["resolved"]["tombstones"] or cid in ignored:
            continue
        db = client.find_tasks_db_under(cid)
        if not db:
            ignored.add(cid); continue
        cache[cid] = {"label": child.get("title", cid), "role": "tasks",
                      "tasks_db": db, "cached_at": date.today().isoformat()}
        summary["added"].append(cid)
    map["resolved"]["ignored"] = sorted(ignored)
    return summary

def reconcile_due_groups(map: dict, client, today, warnings=None) -> None:
    """Reconcile each group area at most once per calendar day (daily TTL gate)."""
    resolved = map.setdefault("resolved", {})
    stamps = resolved.setdefault("reconciled", {})
    groups = resolved.get("groups", {})
    stamp = today.isoformat()
    for area_key, area in map.get("areas", {}).items():
        if "group" not in area:
            continue
        if not groups.get(area_key):       # empty/undiscovered -> discovery handles it
            continue
        if stamps.get(area_key) == stamp:   # already reconciled today
            continue
        try:
            reconcile_group(map, client, area_key)
            stamps[area_key] = stamp
        except WorkspaceUnavailable:
            raise
        except Exception as exc:
            if warnings is not None:
                warnings.append(f"reconcile {area_key} failed: {exc}")


def drop_stale(map: dict, source_id: str) -> None:
    for area in map["resolved"]["groups"].values():
        for cid, entry in list(area.items()):
            if entry.get("tasks_db") == source_id:
                area.pop(cid)
