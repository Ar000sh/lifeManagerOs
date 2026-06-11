# Integrations

Track which tools are connected and how to use them. Update this file when new tools are added.

---

## Notion
- **Status:** Connected
- **MCP prefix:** `mcp__claude_ai_Notion__`
- **Key tools:** `notion-search`, `notion-fetch`, `notion-create-pages`, `notion-update-page`
- **Source of truth for:** all tasks, modules, work schedule
- **Notes:** Must be connected to the THIRD "Workspace von Aroosh Al-arashi". See `notion.md` for full map.

---

## Google Calendar
- **Status:** Connected
- **MCP prefix:** `mcp__claude_ai_Google_Calendar__`
- **Key tools:** `list_events`, `create_event`, `update_event`, `delete_event`, `suggest_time`
- **Source of truth for:** timed events, reminders, appointments
- **Notes:** Notion deadlines/exams should ideally also be in Google Calendar as reminders. When adding an exam or important deadline in Notion, offer to also create a Calendar event.

---

## Adding New Tools
When a new integration is added, add an entry here with:
- Status
- MCP prefix or access method
- What it's the source of truth for
- Any quirks or notes
