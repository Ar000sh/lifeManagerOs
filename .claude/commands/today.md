# /today — Daily Briefing

Give Aroosh a structured morning briefing for today. Pull live data — don't summarize from memory.

**Notion reads:** Prefer the `notion-api` MCP server (official Notion API — supports real property filters). Query the relevant database filtered by Due Date / Status / date ranges directly, instead of semantic search + per-page fetch. Use semantic search only as a fallback if a filtered query fails.

## Steps

1. **Get today's date** in Europe/Berlin time.

2. **Google Calendar** — fetch today's events via the available Google Calendar MCP (its list-events tool). Show time + title for each.

3. **University deadlines today or overdue** — search Notion University Tasks (collection `580c2d1d-8813-4800-92a1-9db78568a1ca`) for items with Due Date = today or earlier, Status ≠ Done.

4. **Work shift today** — check Work Schedule (collection `55f90404-8783-412a-9f9d-e6d5011bcc7a`) for entries with Date = today.

5. **Business tasks due today** — check all four business Tasks DBs for tasks with Due Date = today or Status = "This Week":
   - Laundromat Hannover (`fdffad80-a34c-44a0-a9ed-afb05acd232e`)
   - Van Company Czech Republic (`ae28ef1d-5dec-45d2-b3ab-8132214d5361`)
   - TBHShop — Trip Back Home (`6905803e-faa1-444a-877e-296a5dbfcdbd`)
   - Evening Dresses Export (`b0cf87a9-fa93-4dd2-8d9c-b883f925537a`)

## Output Format

Keep it tight. Use this structure:

---
**📅 [Day, Date]**

**🗓 Calendar**
- [time] Event name
- (none if empty)

**🎓 University**
- [URGENT if overdue] Task name — Due: date (Module)
- (none if empty)

**💼 Work**
- Shift: Start–End (or "No shift today")

**🚀 Business**
- Task name [Priority] — Business name
- (none if empty)

**Quick note:** [one sentence observation — e.g. "2 exams this week, plan study time" or "nothing urgent today"]
---
