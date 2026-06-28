from dataclasses import dataclass
from datetime import date
from .resolver_schema import schema_for

@dataclass
class ResolvedSource:
    source_id: str; role: str; area_key: str
    area_label: str; area_emoji: str; schema: dict
    source_label: str | None = None

def iter_areas(map: dict) -> list[dict]:
    return [{"key": k, "label": a.get("label", k), "emoji": a.get("emoji", "")}
            for k, a in map.get("areas", {}).items()]

def _anchor_id(map: dict, anchor: str) -> str:
    return map.get("anchors", {}).get(anchor, anchor)

def resolve_sources(map: dict, client, role: str) -> list[ResolvedSource]:
    out: list[ResolvedSource] = []
    for key, area in map.get("areas", {}).items():
        label, emoji = area.get("label", key), area.get("emoji", "")
        for src in area.get("sources", []):
            if src.get("role") != role:
                continue
            sid = _anchor_id(map, src["anchor"])
            # schema for an anchored source is keyed by the anchor NAME (ids live
            # only in `anchors`); the resolved id `sid` is used only for queries.
            out.append(ResolvedSource(sid, role, key, label, emoji,
                                      schema_for(map, src["anchor"], role)))
        group = area.get("group")
        if group and any(cs.get("role") == role for cs in group.get("child_sources", [])):
            for sid, label_ in _resolve_group(map, client, key, group, role):
                out.append(ResolvedSource(sid, role, key, label, emoji,
                                          schema_for(map, sid, role), source_label=label_))
    return out

def _resolve_group(map, client, area_key, group, role):
    cache = map.setdefault("resolved", {}).setdefault("groups", {}).setdefault(area_key, {})
    if not cache:  # cache miss -> enumerate once, write back (keyed by ID)
        #child pages we looked at before and found they have no tasks database inside
        ignored = set(map["resolved"].setdefault("ignored", []))
        #children that were deleted
        tombstones = map["resolved"].setdefault("tombstones", {})
        for child in client.get_block_children(_anchor_id(map, group["under"])):
            cid = child["id"]
            if cid in ignored or cid in tombstones:
                continue
            db = client.find_tasks_db_under(cid)
            if not db:
                ignored.add(cid); continue
            cache[cid] = {"label": child.get("title", cid), "role": role,
                          "tasks_db": db, "cached_at": date.today().isoformat()}
        map["resolved"]["ignored"] = sorted(ignored)
    for cid, entry in cache.items():
        if entry.get("role") == role:
            yield entry["tasks_db"], entry["label"]

def resolve_named(map, client, area_key, name):
    resolve_sources(map, client, "tasks")  # ensure enumerated
    cache = map["resolved"]["groups"].get(area_key, {})
    area_label = map.get("areas", {}).get(area_key, {}).get("label", area_key)
    name_l = name.lower()
    for cid, entry in cache.items():
        if name_l in entry["label"].lower():
            return ResolvedSource(entry["tasks_db"], entry["role"], area_key,
                                  area_label, "", schema_for(map, entry["tasks_db"], entry["role"]),
                                  source_label=entry["label"])
    return None
