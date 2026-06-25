# /week — Weekly Overview

Structured view of the current week (Mon–Sun, Europe/Berlin). Pull live data.
**Resolve all Notion targets via `context/resolver.md`.** Prefer filtered Notion API
queries over semantic search.

## Steps
1. Determine the current week (Monday–Sunday) in Europe/Berlin.
2. **Calendar** — fetch all events for the week via the Google Calendar MCP list-events
   tool.
3. **Work shifts** — resolve the `schedule` source; fetch entries whose `date` falls in
   the week.
4. **University deadlines** — resolve the `university_tasks` source; fetch items whose
   `due_date` or `exam_date` is within the week and `status` ≠ `done`; sort ascending.
5. **Business tasks** — resolve every `business_tasks` source (all businesses); fetch
   items whose `status` = the role's `this_week` value or whose `due_date` is within the
   week.
6. Self-heal failed sources per the resolver; flag any that stay broken.

## Output Format
Group by day; skip empty days.
---
**📆 Week of [Mon Date] – [Sun Date]**

**Monday, [Date]**
- 🗓 [time] Calendar event
- 💼 Work: [Start–End] or —
- 🎓 [Task name] due (Module)
- 🚀 [Business task] [Priority]

… (each day) …

**Summary**
- X university deadlines, X business tasks, X work shifts
- [one actionable note]
---
