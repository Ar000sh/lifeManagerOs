# /week — Weekly Overview

Give Aroosh a structured view of the current week. Pull live data from Notion and Google Calendar.

**Notion reads:** Prefer the `notion-api` MCP server (official Notion API — supports real property filters). Query the relevant database filtered by Due Date / Exam Date / Status / date ranges directly, instead of semantic search + per-page fetch. Use semantic search only as a fallback if a filtered query fails.

## Steps

1. Determine the current week (Monday–Sunday) in Europe/Berlin time.

2. **Google Calendar** — fetch all events for the week via the available Google Calendar MCP (its list-events tool).

3. **Work shifts** — fetch Work Schedule (collection `55f90404-8783-412a-9f9d-e6d5011bcc7a`) filtered to this week's dates.

4. **University deadlines this week** — fetch University Tasks (collection `580c2d1d-8813-4800-92a1-9db78568a1ca`) with Due Date or Exam Date within the week, Status ≠ Done. Sort by date ascending.

5. **Business tasks this week** — fetch all four business Tasks DBs for tasks with Status = "This Week" or Due Date within the week:
   - Laundromat Hannover (`fdffad80-a34c-44a0-a9ed-afb05acd232e`)
   - Van Company Czech Republic (`ae28ef1d-5dec-45d2-b3ab-8132214d5361`)
   - TBHShop — Trip Back Home (`6905803e-faa1-444a-877e-296a5dbfcdbd`)
   - Evening Dresses Export (`b0cf87a9-fa93-4dd2-8d9c-b883f925537a`)

## Output Format

Group by day. Skip days with nothing.

---
**📆 Week of [Mon Date] – [Sun Date]**

**Monday, [Date]**
- 🗓 [time] Calendar event
- 💼 Work: [Start–End] or —
- 🎓 [Task name] due (Module)
- 🚀 [Business task] [Priority]

**Tuesday, [Date]**
...

**Summary**
- X university deadlines, X business tasks, X work shifts
- [One actionable note — e.g. "Heavy Wednesday — exam + shift. Consider moving task X."]
---
