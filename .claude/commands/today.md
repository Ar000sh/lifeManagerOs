# /today — Daily Briefing

Structured morning briefing for today. Call the **`mcp__lifeos__get_today`** tool and format
its JSON — do NOT resolve Notion yourself.

## Steps
1. Call `mcp__lifeos__get_today` (no arguments).
2. If it returns `{"error": "reconnect_notion"}`, reply that Notion looks disconnected and to
   reconnect — do not print an empty briefing. If `{"error": "no_map"}`, tell the user to run
   `/refresh-notion` first.
3. Otherwise format the payload: `date`, `areas[]` (each `label`, `emoji`, `tasks[]`,
   `key_dates[]`, `shift`), `events[]`, and `warnings[]`.

## Rendering rules
- **Tasks:** show `title`; prefix **URGENT** when `overdue` is true; append `source_label`
  (the venture) when present; show `fields.priority` in brackets if present.
- **Key dates:** render the area's `key_dates[]` in a single **"📌 Key dates"** section as
  `• {label} — {title}`. Do NOT also print a highlighted date inline under its task.
- **Shift:** render `shift` as `Start–End` (or "No shift today").
- **Events:** the top-level `events[]` are today's calendar (time + title).
- **Warnings:** if `warnings[]` is non-empty, add a short "⚠ Note: …" line; never hide a
  failure silently.

## Output Format
---
**📅 [Day, Date]**

**🗓 Calendar**
- [time] Event name  (or "none")

**🎓 University** (and each area with content)
- [URGENT if overdue] Task name [Priority]  (or "none")

**💼 Work**
- Shift: Start–End  (or "No shift today")

**📌 Key dates**
- [Label] — [Task]  (omit the section if none)

**Quick note:** [one-sentence observation, incl. any warning]
---
