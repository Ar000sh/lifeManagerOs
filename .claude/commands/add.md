# /add — Add a record

Add a task, university item, exam, work shift, module, or calendar event to the right
place. **Resolve all Notion targets via `context/resolver.md`.** This skill creates
**records** (rows) only — it does NOT create new businesses, databases, sections, or
views (that is the workspace-provisioning project).

## Routing
| What the user says | Role / destination |
|---|---|
| task / to-do for a business | `business_tasks` of that business (resolve by name under the `businesses` rule) |
| university task / assignment / study session | `university_tasks` |
| exam | `university_tasks`, Type = Exam, set `exam_date` |
| work shift | `schedule` |
| new module / course | `modules` |
| meeting / appointment / event with a time | Google Calendar |
| reminder | Google Calendar |

If the destination is unclear, ask ONE question: "Business, University, Work, or Calendar?"
If a business name is given but not yet in the map, resolve-on-miss (enumerate under
`business_root`); if it does not exist, say so — do NOT create a new business here.

## Creating in Notion
Use `notion-create-pages` into the resolved DB. Set columns via the destination role's
`db_role_schemas` (never assume column names). Defaults: set `title`; set `status` to a
sensible start value; set `priority` = Medium if not given; set `due_date` if mentioned — set each only when the destination role's `db_role_schemas` defines it.
For a university task tied to a module: resolve `modules`, search the module page, set the
`module` relation. For exams set both `due_date` (prep-by) and `exam_date` if known.

## Creating in Google Calendar
Use the Google Calendar MCP create-event tool. Always set start + end (default 1h).
Timezone: Europe/Berlin.

## Cross-posting
If adding an exam or important deadline in Notion, ask: "Also add a reminder in Google
Calendar?"

## Confirm
One line: "Added **[Name]** to [destination] — [key detail]."
