<!-- GENERATED from the Life-OS map by /refresh-notion — do not hand-edit -->
# Notion Workspace Map

Workspace: **"Workspace von Aroosh Al-arashi"** (id `8a0121c0-adad-815e-ad56-000383497543`) —
the THIRD of three identically named workspaces. If searches return empty, the wrong
workspace is connected. Ask the user to reconnect the Notion MCP.

- **Map file:** `context/maps/1672283963.json` (identity = the configured Telegram chat id).
  This is the durable map the `lifeos` MCP server reads. Rebuilt by `/refresh-notion`.
- **Root page (My Life OS):** `17f640b8-4c57-4cdb-8cb8-7de20d282e14`

> **IDs are database *block* ids**, not data-source (`collection://`) ids. The `lifeos`
> engine queries the raw Notion API (`/v1/databases/{id}/query`, version `2022-06-28`),
> which accepts the database block id and 404s on the collection id.

---

## Area Tree

```
📋 My Life OS  (17f640b8-4c57-4cdb-8cb8-7de20d282e14)
├── 🚀 Business  (area: ventures)   — group under business_root 02b35e4e-891d-4c3b-a8a1-8b5f3a968c34
│   │                                 each child page with a Tasks DB is a venture (role: tasks)
│   ├── 💡 Laundromat Hannover          page 39b55afa-…8e38  ·  tasks_db cee0a804-8964-4c28-baa7-9278c617e8ab
│   ├── 🚐 Van Company Czech Republic   page b5397190-…0790  ·  tasks_db 3f594dbd-1de8-4416-8cc7-fece37d0b2ee
│   ├── 🛍️ TBHShop — Trip Back Home     page 37b121c0-…049d  ·  tasks_db 31b50c35-8743-4de9-b408-2cc7d0ba7b6a
│   ├── 👗 Evening Dresses Export       page 37b121c0-…1eaa  ·  tasks_db 7e1138dd-fcad-47bd-8847-a4d108aa16e4
│   └── 🧪 ZZ Test Bakery               page 38b121c0-…eca1  ·  tasks_db 56fdecc1-dc21-427a-a62f-8a60e3ebe5cb
├── 🎓 University  (area: university)   — section 25a31bbe-c66a-42d7-abd1-063ddf316f0e
│   ├── University Tasks DB  (role: tasks)     7736e225-5313-4e66-9f8c-aec95cb8f090
│   └── Modules DB  (role: catalog)            d507b171-1f45-44db-a254-b6eabf9eff19
└── 💼 Work  (area: work)
    └── Work Schedule DB  (role: schedule)     b86b2485-e6f2-47e1-9291-b9cbce856add
```

**Ignored** (child pages under Business with **no** Tasks DB — not task sources; a future
`/refresh-notion` re-probes them):

- Goethe A1 · `37e121c0-…1c28` — language course, blank page
- AI-Driven Software Development · `385121c0-…2f3a` — venture idea, description only (no Tasks DB yet)
- Life OS Manager · `385121c0-…8bdd` — venture idea, description only (no Tasks DB yet)
- test · `38a121c0-…cecd` — scratch page

> Ventures live in `resolved.groups.ventures`; new ones are auto-discovered on the daily
> reconcile once they contain a Tasks DB. **AI-Driven Software Development** and **Life OS
> Manager** are real ideas parked as ignored until they get their own Tasks DB.

---

## Source Schemas

Each source declares a **core block** (engine-recognized: `title`, `due_date`/`date`,
`done_predicate`, optional `week_predicate`) plus typed **fields**. ⭐ marks a **key date**
(surfaces as a reminder in `/today` on the exact day it falls).

### Business Tasks — `child_schema_defaults.tasks`
Shared shape every venture inherits (Laundromat, Van, TBHShop, Evening Dresses, ZZ Test Bakery).
These are planning ventures — mostly not yet launched.

| Role key | Column | Type | Notes |
|---|---|---|---|
| title | Name | title | required |
| due_date | Due Date | date | required |
| done_predicate | Status | select | `= "Done"` → complete |
| week_predicate | Status | select | `= "This Week"` |
| status | Status | select | Backlog, This Week, In Progress, Done, Blocked |
| priority | Priority | select | High, Medium, Low (default **Medium** on add) |
| type | Type | select | Epic, Milestone, Story, Task |
| business | Business | rich_text | free text |
| notes | Notes | rich_text | free text |
| parent | Parent | relation | self-referential (sub-tasks) |

### University Tasks — anchor `university_tasks_db`  (role: tasks)

| Role key | Column | Type | Notes |
|---|---|---|---|
| title | Name | title | required |
| due_date | Due Date | date | required (Notion reminder 3 days before, 09:00 Berlin) |
| done_predicate | Status | select | `= "Done"` → complete |
| status | Status | select | Not Started, In Progress, Done (no "This Week") |
| priority | Priority | select | High, Medium, Low |
| type | Type | select | Exam, Assignment, Task, Study Session |
| exam_date ⭐ | Exam Date | date | **key date** (Notion reminder 7 days before, 09:00 Berlin) |
| grade | Grade | rich_text | — |
| module | Module | relation | → Modules DB |
| notes | Notes | rich_text | — |

Read-only rollups **Module (Name)** and **Semester Label** exist in Notion but are excluded
from the map (synced/not queryable — never write them).

### Work Schedule — anchor `work_schedule_db`  (role: schedule)

| Role key | Column | Type | Notes |
|---|---|---|---|
| title | Name | title | shift name / label |
| date | Date | date | required |
| start | Start Time | rich_text | e.g. "09:00" |
| end | End Time | rich_text | e.g. "17:00" |
| day | Day | select | Monday … Sunday |
| recurring | Recurring | checkbox | `"__YES__"` = true |
| notes | Notes | rich_text | — |

### Modules — anchor `modules_db`  (role: catalog)

| Role key | Column | Type | Notes |
|---|---|---|---|
| title | Name | title | required |
| semester | Semester | select | WS 2024/25, SS 2025, WS 2025/26, SS 2026 |
| status | Status | select | Active, Completed, Upcoming |
| credits | Credits | number | — |
| professor | Professor | rich_text | — |
| notes | Notes | rich_text | — |

Known modules with dedicated task views: Security, Machine Learning, Geometry, Logic.
**SS 2026 (current):** Security 2, Deep Learning, Programming Paradigms — weekly lecture/
exercise slots live in **Google Calendar** (recurring, color-coded) and each module's Notes,
not the Modules DB (Notion has no recurring rows).
