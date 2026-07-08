# /week — Weekly Overview

Structured view of the current week (Mon–Sun, Europe/Berlin). Call **`mcp__lifeos__get_week`**
and format its JSON — do NOT resolve Notion yourself.

## Steps
1. Call `mcp__lifeos__get_week` (no arguments).
2. On `{"error": "reconnect_notion"}` → say Notion looks disconnected. On `{"error":
   "no_map"}` → tell the user to run `/refresh-notion`.
3. Otherwise format: `start`, `end`, `days[]` (each `date`, `tasks[]`, `key_dates[]`, `shift`,
   `events[]`), `summary` (`tasks`, `key_dates`, `shifts`), `warnings[]`.

## Rendering rules
- Group by day (skip empty days). Per day: calendar events (time+title), work `shift`
  (`Start–End`), tasks (`title`, area/venture, `[status]`), and key dates as `• {label} —
  {title}` under their day.
- Never re-print a key date inline among a task's fields.
- End with the `summary` counts and a one-line actionable note (include any `warnings`).

## Output Format
---
**📆 Week of [Mon Date] – [Sun Date]**

**Monday, [Date]**
- 🗓 [time] Calendar event
- 💼 Work: [Start–End]
- 🎓/🚀 [Task] [status] — [area/venture]
- 📌 [Label] — [Task]   (key date on this day)

… (each day) …

**Summary**
- [summary.tasks] tasks, [summary.key_dates] key dates, [summary.shifts] shifts
- [one actionable note]
---
