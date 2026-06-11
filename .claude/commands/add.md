# /add — Add Something

Add a task, event, shift, or module to the right place. The user will describe what they want to add after `/add`.

## Routing Logic

Read the user's input and decide where it belongs:

| What they say | Where it goes |
|---|---|
| task / to-do for Laundromat or Van Company | Business Tasks (correct collection) |
| university task / assignment / study session | University Tasks |
| exam | University Tasks with Type = Exam + set Exam Date |
| work shift / I'm working | Work Schedule |
| new module / course | Modules |
| meeting / appointment / event with a time | Google Calendar |
| reminder | Google Calendar |

If the destination is unclear, ask ONE question: "Is this for Business, University, Work, or Calendar?"

## Creating in Notion

Use `notion-create-pages`. Required fields vary by database — see `context/notion.md` for schemas.

- Always set at least: `Name`, `Status`, `Due Date` (if mentioned), `Priority` (default Medium if not specified).
- For university tasks linked to a module: first search for the module with `notion-search` to get its URL, then set the `Module` relation.
- For exams: set both `Due Date` (when to submit/prepare by) and `Exam Date` (actual exam day) if both are known.

## Creating in Google Calendar

Use `mcp__claude_ai_Google_Calendar__create_event`.
- Always include a start time and end time. If end time not given, default to 1 hour.
- Timezone: Europe/Berlin.

## Cross-posting

If the user adds an exam or important deadline in Notion, ask: "Want me to also add a reminder in Google Calendar?"

## Confirm

After creating, respond in one line:
"Added **[Name]** to [destination] — [key detail like due date or time]."
