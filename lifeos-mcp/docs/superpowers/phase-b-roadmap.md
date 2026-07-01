# Phase B — Roadmap & Status (index)

One-glance view of what's done and what's left to wire the `lifeos` MCP server into the bot.
Tick tasks as they complete. Details live in the linked spec/plans.

**Spec:** `specs/2026-07-01-phase-b-bot-integration-design.md` (design + locked decisions)
**Branch:** `feat/dynamic-skills` (local, unpushed)

## Done (Phase A + design)
- [x] lifeos MCP server + 5 tools, dynamic typed schema, key-dates-as-reminders — **98 tests green**
- [x] Phase B design spec + both decisions locked (keep npx servers; `/add` → lifeos `create_event`)
- [x] Persistence decision: identity-keyed **Azure Blob** map store (chat id → user id)

## Plan 1 — Foundation (persistence + wiring) — `plans/2026-07-01-phase-b-foundation.md`
Code + infra, all TDD/validated. **Not started.**
- [ ] T1 `MapStore` + `FileMapStore` + `MapNotFound`
- [ ] T2 `AzureBlobMapStore` (managed identity) + azure deps
- [ ] T3 `Settings` identity + store selection + `build_store`
- [ ] T4 `server.py` load/save per identity; `no_map`
- [ ] T5 `mapctl` push/pull (map ↔ store)
- [ ] T6 `infra/storage.tf` + doc (account, `maps` container, VM blob role) — *Aroosh applies via CI/CD*
- [ ] T7 Register lifeos in `agent_runner` + thread chat id (`LIFEOS_IDENTITY`)

## Plan 2 — Cutover (map regen + thin skills + live) — `plans/2026-07-01-phase-b-cutover.md`
Authoring + manual. **Not started; depends on Plan 1.**
- [ ] T1 Rewrite `/refresh-notion` → new-shape typed map + key-date prompt
- [ ] T2 Thin `/today` onto `get_today`
- [ ] T3 Thin `/week` onto `get_week`
- [ ] T4 Thin `/add` onto `add_record` + `create_event`
- [ ] T5 Deprecate `context/resolver.md`
- [ ] T6 Thread chat id into the multi-turn `LiveAgentClient`
- [ ] T7 Regenerate the real map + `mapctl push` (with Aroosh)
- [ ] T8 Live validation through the bot vs real Notion (with Aroosh)

## Known blocker (resolved by Plan 2 T1+T7)
The live `context/lifeos.map.json` is **old-shape**; the server needs new-shape. Regenerate via
the rewritten `/refresh-notion` — never hand-edit.
