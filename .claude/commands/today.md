# /today — Daily Briefing

Structured morning briefing for today. Pull live data — don't summarize from memory.
**Resolve all Notion targets via `context/resolver.md`.** Prefer filtered Notion API
queries over semantic search.

## Steps
1. Get today's date in Europe/Berlin.
2. **Calendar** — fetch today's events via the Google Calendar MCP list-events tool.
   Show time + title.
3. **Tasks (all task roles)** — resolve every source for the map's `task_roles`
   (each business's `business_tasks` DB + the `university_tasks` DB). For each, query
   items where the role's `due_date` (or `exam_date` for university) is today or earlier
   and `status` ≠ the role's `done` value. Use each role's `db_role_schemas` for the real
   property names.
4. **Work shift today** — resolve the `schedule` source (work_schedule_db) and find
   entries where the `date` property = today.
5. If a source fails to resolve, self-heal per the resolver; if it still fails, include
   the rest and flag the broken one rather than aborting.

## Output Format
---
**📅 [Day, Date]**

**🗓 Calendar**
- [time] Event name  (or "none")

**🎓 University**
- [URGENT if overdue] Task name — Due: date (Module)  (or "none")

**💼 Work**
- Shift: Start–End  (or "No shift today")

**🚀 Business**
- Task name [Priority] — Business name  (or "none")

**Quick note:** [one-sentence observation]
---
