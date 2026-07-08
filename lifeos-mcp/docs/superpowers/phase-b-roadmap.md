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
Code + infra, all TDD/validated. **Done (code-complete, suites green).**
- [x] T1 `MapStore` + `FileMapStore` + `MapNotFound`
- [x] T2 `AzureBlobMapStore` (managed identity) + azure deps
- [x] T3 `Settings` identity + store selection + `build_store`
- [x] T4 `server.py` load/save per identity; `no_map`
- [x] T5 `mapctl` push/pull (map ↔ store)
- [x] T6 `infra/storage.tf` + doc (account, `maps` container, VM blob role) — applied
- [x] T7 Register lifeos in `agent_runner` + thread chat id (`LIFEOS_IDENTITY`)

## Plan 2 — Cutover (map regen + thin skills + live) — `plans/2026-07-01-phase-b-cutover.md`
Authoring + manual. **T1–T6 done (uncommitted in working tree); T7 half-done; T8 in progress.**
- [x] T1 Rewrite `/refresh-notion` → new-shape typed map + key-date prompt
- [x] T2 Thin `/today` onto `get_today`
- [x] T3 Thin `/week` onto `get_week`
- [x] T4 Thin `/add` onto `add_record` + `create_event`
- [x] T5 Deprecate `context/resolver.md`
- [x] T6 Thread chat id into the multi-turn `LiveAgentClient`
- [x] T7 Regenerate the real map + `mapctl push` — map built 2026-07-04
      (`context/maps/1672283963.json`, new-shape ✓); **pushed to blob 2026-07-07**
      via `mapctl push` (human blob-data grant `map_admin_storage` added to `storage.tf`,
      applied locally into shared remote state → CI will see it as already-present)
- [ ] T8 Live validation — local probe 2026-07-06: `get_today`/`get_week` green vs real
      Notion + Calendar (classic `/v1/databases/{id}/query` works; no client change needed).
      Required fix: `calendar_client.py` now reads the @cocal token format (tests added).
      **Still open:** VM managed-identity blob check, Telegram parity run (`/today` `/week`
      `/add`), self-heal checks, sign-off.

## Known issues found at live validation
- `telegram-bot/.env` `GOOGLE_OAUTH_CREDENTIALS` / `GOOGLE_CALENDAR_MCP_TOKEN_PATH` still
  point at the old repo path (`C:\Users\Tariq\Desktop\ai\lifeManagerOs\…`) — breaks local
  runs; the Docker/VM env is unaffected.
- `get_today` returns ~27 `missing required due_date/title` warnings from real tasks with
  no due date — expected contract, but `/today` will render a noisy "⚠ Note" line; consider
  muting per-task no-due-date warnings.
