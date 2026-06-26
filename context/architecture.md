# Life-OS Architecture & Direction

Living design doc for where the Life-OS assistant is headed. Captures the agreed
direction so any session can continue. **Not yet built — this is the plan for the next
phase, after the dynamic-skills foundation.**

---

## Where we are now

- **Dynamic-skills foundation** (branch `feat/dynamic-skills`, validated, not merged):
  `/today`, `/week`, `/add`, `/refresh-notion` resolve Notion at runtime via
  `context/lifeos.map.json` + `context/resolver.md` — no hardcoded IDs. This is the
  working **prototype/spec** of the resolution behavior.
- **Next phase (this doc):** turn that prototype into an **agent + tools** product backed
  by **our own `lifeos` MCP server**, plus a **knowledge vault**.

---

## The three layers

1. **Agent (brain) — Claude.** Understands the natural-language request, decides what to
   do, picks the tool(s) with clean arguments, chains multi-step actions, handles
   ambiguity, writes the response. We are NOT replacing the agent — keeping a real
   assistant is the whole point.
2. **Live data plane — the `lifeos` MCP server's action/data tools.** Each tool does the
   deterministic work: read the map, resolve real IDs, call Notion/Google APIs directly,
   return clean results. Current truth + actions. Cheap, reliable, always fresh.
3. **Knowledge vault — durable understanding.** Goals, priorities, relationships,
   preferences, history, derived insights, and the structural map. Served via
   knowledge tools (`recall` / `remember` / `get_insights`). Makes the agent *smart*.

---

## The reliability rule (most important)

> **Volatile facts → ALWAYS fetched live via MCP tools. Durable understanding → the
> vault. Never store volatile truth in the vault.**

The agent combines them: the vault supplies *meaning and priorities*, the live plane
supplies *what is actually true right now*. Mixing the two — answering operational
questions from memory instead of checking — is exactly what makes an assistant
unreliable, so the design forbids it. The vault therefore **depends on** the MCP to stay
grounded; it makes the MCP more needed, not less.

Example: vault = "Van Company is the stalled priority, launch goal Q1 2027"; live =
"3 open tasks, all Backlog"; agent = "Van Company's been quiet — all 3 tasks are still
Backlog; given the Q1 goal, pull one into This Week?"

---

## What lives where

| Vault (durable — makes it smart) | Live via MCP (current — keeps it correct) |
|---|---|
| Goals/strategy & priorities per venture | Tasks, statuses, due dates |
| People, relationships, contacts | Calendar events, work shifts |
| Preferences & working patterns | Module / exam state |
| Decisions + history (the "why") | Anything that changes day-to-day |
| Derived insights / patterns | |
| Structural map (`lifeos.map.json` = first slice) | |

---

## The `lifeos` MCP server

One toolbox, two kinds of tools:

- **Action/data tools:** `get_today`, `get_week`, `add_record`, `update_record`,
  `query_records`, `create_event`, `move_event`, …
- **Knowledge tools:** `recall(topic)`, `remember(fact)`, `get_insights(area)`, …

Built as MCP (not logic buried in `bot.py`) so the **same toolbox serves the Telegram
bot, interactive Claude Code, and Claude desktop** — one implementation. The agent keeps
raw Notion/Google access for novel one-offs, so tools accelerate common actions without
caging it. Natural home for **multi-user**: per-user map + vault + their own keys.

---

## Keeping the vault fresh

- Store only durable things; derive volatile things live.
- Agent writes learnings back via `remember(...)`.
- Periodic reconciliation for structural parts — like `/refresh-notion` for the map.
- **Implementation v1:** structured markdown/JSON memory files (transparent, versionable
  — same pattern as Claude's own memory). Add vector/graph retrieval later only if it
  outgrows files.

---

## How current artifacts map in

- `context/lifeos.map.json` → the server's **config** + the structural slice of the vault.
- `context/resolver.md` → the server's **resolution code**.
- The markdown skills (`/today`, …) → thin **intent descriptions** backed by tools, or
  retired once tools carry the logic.

---

## Open questions (resolve in a focused brainstorm before building)

1. **Vault storage v1:** markdown/JSON memory files (recommended start) vs vector store
   vs knowledge graph.
2. **Vault scope v1:** which durable categories to capture first (goals? preferences?
   relationships?).
3. **Server placement:** where the MCP server runs relative to `bot.py`; how config + keys
   are passed (single-user now, multi-user later).
4. **First tool set:** recommended — `get_today`, `add_record`, `update_record`, calendar
   `create`/`move`, `recall`/`remember`.
5. **Sync cadence** for structural reconciliation.

---

## Next step

A focused **brainstorm → spec → plan** for "`lifeos` MCP server v1 (+ vault v1)". Do not
start implementation until that brainstorm settles the open questions above.
