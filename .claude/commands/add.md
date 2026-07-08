# /add — Add a record

Add a task, university item, work shift, module, or calendar event to the right place using
the **lifeos** tools. Creates **records** (rows) and calendar events only — never new
databases/sections/businesses.

**Use ONLY `mcp__lifeos__*` tools in this skill.** Never call the raw `mcp__notion-api__*` or
`mcp__google-calendar__*` servers here — they exist for ad-hoc chat, not `/add`. The lifeos
tools own destination resolution and the timezone/duration defaults; bypassing them is a bug.

## Routing → tool call
| What the user says | Call |
|---|---|
| task / to-do (business or university) | `mcp__lifeos__add_record` role `tasks`, `area` = the venture or area name |
| work shift | `mcp__lifeos__add_record` role `schedule`, `area` = "Work" |
| new module / course | `mcp__lifeos__add_record` role `catalog`, `area` = "University" |
| meeting / appointment / reminder with a time | `mcp__lifeos__create_event` |

`fields` uses the map's declared field keys (e.g. `title`, `due_date`, `priority`, `module`,
`status`). Pass ISO dates. Do NOT guess column names — the tool maps keys to columns.

**Never fabricate field values.** Only pass values the user actually gave. If a required field
is missing (a task always needs a `due_date`), you MUST ask — never invent, guess, or default
it. Inventing a due date is a bug.

## Handling the tool result
- `add_record` success → `{"created": true, "destination": "...", "url": "..."}`.
- `{"created": false, "error": "missing_required", "fields": [...]}` → the record needs a value
  you don't have. **Do NOT invent, guess, or default it** (never make up a `due_date`). Ask the
  user ONE short question for the missing field(s) and **STOP this turn — do not call the tool
  again now.** Only when the user replies with the value, call `add_record` again with it.
- `{"error": "ambiguous_destination" | "destination_not_found", "candidates": [...]}` → ask
  ONE question listing the candidates; retry with the chosen `area`.
- `{"error": "no_map"}` → tell the user to run `/refresh-notion`.
- (If the tool raises an unsupported-field-type error, the map is misconfigured — flag it for
  `/refresh-notion`, don't retry blindly.)

## Calendar
Meetings / appointments / timed reminders ALWAYS go through
**`mcp__lifeos__create_event(title, start, end?, notes?)`** — Europe/Berlin, default 1h.
Do NOT use `mcp__google-calendar__create-event` for `/add`. For an important Notion deadline,
offer: "Also add a calendar reminder?"

## Confirm
One line: "Added **[Name]** to [destination] — [key detail]."
