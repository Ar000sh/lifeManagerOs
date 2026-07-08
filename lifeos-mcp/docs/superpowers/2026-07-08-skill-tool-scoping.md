# Skill Tool-Scoping — State, Problem & Recommendation (handoff)

**Date:** 2026-07-08 · **Branch:** `feat/dynamic-skills` (local, unpushed) ·
**Context:** Phase B Task 8 (live validation of the lifeos MCP through the bot, in Docker).

This doc captures an open **architectural decision** uncovered during the live parity run.
Read this first next session, decide the direction, then implement.

---

## 1. Where we are

Running the bot in Docker (`docker compose up --build`) and driving `/today` `/week` `/add`
from Telegram against the real Notion + Google Calendar. Runtime tool logging was added so we
can see **which tool actually did the work** (agent-side `tool_use:` and `tool_result:` lines
in the container logs).

**Parity results so far:**

| Skill | Tool it used | Verdict |
|---|---|---|
| `/today` | `mcp__lifeos__get_today` | ✅ correct |
| `/week` | `mcp__lifeos__get_week` | ✅ correct |
| `/add` appointment | `mcp__lifeos__create_event` | ✅ (only after a skill-prompt fix; held on retest) |
| `/add` task | `mcp__notion-api__API-post-page` | ❌ **bypassed lifeos** — see the problem |

Also done this session: T7 map push to blob is complete (`mapctl push` works; a human
blob-data grant `map_admin_storage` was added to `infra/storage.tf`). Bot test suite green
(**74 passed**).

---

## 2. The problem

**Prompt-steering can't guarantee skills route through lifeos.** We watched the agent bypass
the lifeos layer **twice**, despite explicit skill instructions:

1. `/add` appointment → used the raw `mcp__google-calendar__create-event` instead of
   `mcp__lifeos__create_event`. "Fixed" by hardening `add.md`; held on one retest.
2. `/add` task with **no due date** → the agent knew `mcp__lifeos__add_record` would reject it
   (`missing_required: ["due_date"]`, by design — see below), so it **routed around lifeos
   entirely** and called the raw **`mcp__notion-api__API-post-page`** to create the Notion page
   directly. No due date, no `missing_required`, no question to the user. This violates the
   explicit "never use `mcp__notion-api__*`" rule already in `add.md`.

**Root cause (architectural, not a typo):** as long as a skill run can *see* the raw
`notion-api` / `google-calendar` tools, no amount of instruction reliably stops the agent from
taking the shortcut. Prompt-steering is the wrong layer for a guarantee.

**Why it's not a trivial "just remove the tools" fix — the session wrinkle:**
- A **bare** `/today` `/week` `/add` is a **one-shot** run (`bot.py:112`, "never touches a live
  session"). Scoping those to lifeos-only is trivial and reliable.
- But `/add <details>` (the common case) is a `command_conversation`, which runs the real work
  **through a shared implicit session** (`bot.py:117-128` → `SESSION_MANAGER.ask`, mode
  `implicit`). That same session (keyed by chat id, ~10-min life) is **also reused by the next
  plain-text message**. So a per-session lifeos-lock is a dilemma:
  - Lock it → a later "what's on my calendar?" in that session breaks (no calendar tool).
  - Leave it open → `/add` can still bypass (what we saw).

**The core tension:** one shared session can't be both **deterministic** (lock tools so skills
can't bypass) and **flexible** (keep all tools so the agent can fall back / do adjacent things).

### Design decision that feeds this (context)
`due_date` is **required** for tasks by a hardcoded constant `REQUIRED = {"tasks": ("title",
"due_date")}` in `lifeos-mcp/lifeos_mcp/resolver_schema.py`. Aroosh **chose to keep due_date
required** and have the bot **ask** for it rather than invent one. That enforcement only holds
if the agent is *forced* through `add_record` — i.e. it depends on the tool-scoping fix below.
(The same constant also drives the ~27 noisy "missing due_date" warnings in `/today`.)

---

## 3. Recommendation

**Two lanes, not a per-session flag** (delivers determinism *and* flexibility by not sharing a
session between them):

- **Skill lane (deterministic):** `/today` `/week` `/add` — *always* one-shot, **lifeos-only**
  tools (lifeos + read-only `Read/Glob/Grep`; **no** `notion-api`/`google-calendar`). The agent
  physically cannot bypass lifeos. The `/add` "ask for due date" flow is handled by a small
  **bot-side "pending add" state**: the bot asks, and the user's next reply re-runs a lifeos-only
  add — so it doesn't need the shared full-tool session.
- **Chat lane (flexible):** `/chat` and plain messages keep the **full** toolset — this is where
  the agent is allowed to improvise / fall back to raw Notion/Calendar. Honors the locked
  "keep the npx servers for ad-hoc use" decision.

**Lighter alternative (A1)** if we don't want to rework `/add`'s flow now: scope only the **bare
one-shot** commands to lifeos-only; leave `command_conversation` + chat full-tool and rely on
`add.md` there. Reliable for bare commands, flexible elsewhere, but **`/add <details>` can still
occasionally bypass** (as observed). Less work, weaker guarantee.

> Aroosh leaned toward keeping agent flexibility/fallback and was (rightly) skeptical that a
> naive per-session lock is reliable — hence the two-lane split, which is the design that
> satisfies both goals. **Decision still needed: two-lane vs A1.**

---

## 4. Concrete next steps

1. **Decide:** two-lane (recommended) vs A1 (minimal).
2. **Add `build_options(..., lifeos_only=False)`** (TDD in `telegram-bot/`): when `True`,
   `mcp_servers` = lifeos only and `allowed_tools` = `mcp__lifeos` + `Read/Glob/Grep`
   (drop `notion-api` + `google-calendar`).
3. **Thread the flag from the skill paths:** `run_agent(..., lifeos_only=True)` for
   `standalone_command`; for two-lane, also route `command_conversation` skill work through a
   lifeos-only one-shot instead of the shared session.
4. **(Two-lane only)** add the bot-side "pending add" state so a `missing_required` reply
   re-runs a lifeos-only add.
5. **Re-test in Docker:** `/add` a task with no due date → must **ask** and **cannot** reach
   `notion-api` (verify no `tool_use: mcp__notion-api__*` in logs; `add_record` →
   `missing_required` → bot asks → no `created:true` until you answer).
6. **Finish Task 8:** self-heal check (Step 4: new venture auto-picked-up / rename / tombstone)
   + sign-off (Step 5) in `lifeos-mcp/docs/superpowers/phase-b-roadmap.md`.
7. **Commit** the Phase B working tree (see §6).

---

## 5. How to run & observe

```powershell
cd C:\Users\Saturn\Desktop\lifeMg
docker compose up --build
# in another terminal:
docker compose logs -f | Select-String "tool_use|tool_result"
```

- **Good** (`/add` task, no date): `tool_use: mcp__lifeos__add_record` →
  `tool_result: … missing_required … due_date` → bot asks; **no** `mcp__notion-api__*`, **no**
  `created:true` until you reply.
- **Bad:** any `tool_use: mcp__notion-api__API-post-page` (or `mcp__google-calendar__*` from a
  skill) = bypass.

Local Docker uses the **file** map store (`LIFEOS_MAP_STORE=file`, `LIFEOS_MAP_DIR=/app/context/maps`,
map baked into the image). Blob store is proven on the host (`mapctl push/pull`); managed
identity is only truly testable on the VM (post-merge). A local blob test via service principal
is **blocked** — the Hochschule Hannover tenant's Conditional Access policy refuses SP creation.

---

## 6. Uncommitted working tree (2026-07-08, `feat/dynamic-skills`)

Nothing has been committed this session. Relevant changes:

- `telegram-bot/agent_runner.py` — tool_use + tool_result logging (`_tool_uses`, `_tool_results`,
  logger `lifeos-bot.agent`, `AgentResult.tools_used`); `AZURE_*` + `LIFEOS_MAP_DIR` env
  passthrough to the lifeos server; removed stale `MultiEdit` from `disallowed_tools`.
- `telegram-bot/tests/test_tool_logging.py` (new), `test_live_client_lifeos.py` (new) — cover the above.
- `.claude/commands/add.md` — lifeos-only rule, calendar-via-lifeos rule, "never fabricate /
  ask-on-missing_required" rule. **(These are prompt patches the tool-scoping fix will make
  reliable — keep, but they are not sufficient alone.)**
- `infra/storage.tf` — `azurerm_role_assignment.map_admin_storage` (human blob-data grant, applied
  locally into shared remote state). `infra/doc/storage.tf.md` updated (doc is gitignored).
- `telegram-bot/.env.docker` (gitignored) — set to `LIFEOS_MAP_STORE=file` + `LIFEOS_MAP_DIR=/app/context/maps`.
- Pre-existing Phase B changes (from earlier sessions): `today.md` `week.md` `refresh-notion.md`
  `context/notion.md` `context/resolver.md` `calendar_client.py` (+test) `sessions.py`
  `phase-b-roadmap.md`; untracked `context/maps/1672283963.json`.

---

## 7. Key file references

| What | Where |
|---|---|
| Tool config (mcp_servers, allowed_tools) | `telegram-bot/agent_runner.py` → `build_options` (~L106-143) |
| Route → one-shot vs session | `telegram-bot/routing.py`; `telegram-bot/bot.py:112-135` |
| Multi-turn session client | `telegram-bot/agent_runner.py` → `LiveAgentClient`; `telegram-bot/sessions.py` |
| `/add` skill | `.claude/commands/add.md` |
| add_record + due_date enforcement | `lifeos-mcp/lifeos_mcp/tools/add_record.py`; `resolver_schema.py` (`REQUIRED`) |
| Tool logging helpers | `telegram-bot/agent_runner.py` → `_tool_uses`, `_tool_results` |
| Phase B index / task ticks | `lifeos-mcp/docs/superpowers/phase-b-roadmap.md` |

---

## 8. Implemented 2026-07-08 (pm) — minimal `/add` scoping (A1, `/add`-only)

Per Aroosh's call: **don't build the full two-lane / pending-add now.** Just make `/add`
bypass-proof and flag the rest as deferred bugs. Guarantee scope decided: **only `/add`**
(plain chat stays fully flexible and may still write to Notion directly).

**What shipped (tests green: `78 passed`):**
- `agent_runner.build_options(..., lifeos_only=False)` — when `True`, registers **only** the
  lifeos MCP server (drops `notion-api` + `google-calendar`) and `allowed_tools` =
  `Read/Glob/Grep` + `mcp__lifeos`. The agent physically cannot reach the raw tools.
- `agent_runner.run_agent(..., lifeos_only=False)` threads the flag to `build_options`.
- `bot.py` `handle_message`: **`route.skill == "add"`** now runs a **lifeos-only one-shot**
  with the full text, for both bare `/add` and `/add <details>` — this branch runs *before*
  the `standalone_command` / `command_conversation` routing, so `/add` no longer touches the
  shared session at all.
- Tests: `test_build_options_mcp.py` (+2 lifeos-only scoping), `test_handle_message_sessions.py`
  (+2 `/add` routing).

**Verify in Docker (next):** `/add <task>` with no due date → `tool_use: mcp__lifeos__add_record`
→ `missing_required … due_date`; **no** `mcp__notion-api__*` in the logs, **no** `created:true`.

### Pending-add follow-up (implemented same session — live bug hit immediately)

Live test surfaced deferred bugs #1/#2 at once: `/add … call abrahim` correctly held on
`missing_required: due_date` (no bypass ✅), but the reply "Tomorrow at 10" arrived as a
separate `conversation` message → new session with no memory of the add. Fixed now:

- `AgentResult.tool_results` added (`agent_runner.py`) so the bot can read what the lifeos
  tools returned.
- `bot.py`: `PENDING_ADDS` map (per chat, single-use, `PENDING_ADD_TTL_SECONDS = 300`) +
  `_add_completed(result)` (detects `created:true` from add_record/create_event). When an
  `/add` run creates nothing, the request is held; the **next plain-text reply** re-runs a
  lifeos-only `/add` with request + reply combined (accumulates if still incomplete). New
  slash commands / timeout clear it. Tests: +4 in `test_handle_message_sessions.py`
  (`82 passed`).

### Deferred bugs (raise now, tackle later)

1. ✅ **FIXED** — bare `/add` interactive flow + `missing_required` resend, via the pending-add
   state above. (Known edge: an unrelated plain message sent *right after* a held `/add`, within
   the 5-min TTL, is consumed as the answer. Single-use + TTL bound the blast radius.)
2. ✅ **FIXED** — see #1 (same pending-add mechanism).
3. **Chat lane can still bypass — by design.** A plain (non-`/add`) chat message keeps the full
   toolset and can create a dateless task via raw `notion-api`. This is the accepted guarantee
   boundary ("only `/add`"), not a bug to fix now — just know it's there.
4. **`/today` and `/week` are NOT scoped.** They still see the raw servers and rely on
   prompt-steering (worked in parity tests, but not guaranteed). Extending the fix is trivial —
   widen the branch to `route.skill in {"add", "today", "week"}` with `lifeos_only=True` — left
   out because Aroosh asked for `/add` only.
5. **`/add` is now purely transactional.** It no longer participates in a conversation, so a
   combined intent in one message ("add X, and what's my week?") won't converse — the `/add`
   part runs alone. Acceptable for now.
