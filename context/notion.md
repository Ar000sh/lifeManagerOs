# Notion Workspace Map

Workspace: **"Workspace von Aroosh Al-arashi"** — the THIRD of three identically named workspaces.
If searches return empty, the wrong workspace is connected. Ask user to reconnect Notion MCP.

Root page: `17f640b8-4c57-4cdb-8cb8-7de20d282e14`

---

## Page Tree

```
📋 My Life OS  (17f640b8-4c57-4cdb-8cb8-7de20d282e14)
├── 📆 My Week  (37b121c0-adad-813e-9d50-d3b45c85ed1e)  ← weekly command center: Google Calendar embed (added manually in UI — API can't create embeds) + linked task views (University open / Laundromat this week / Work schedule)
├── 🚀 Business  (02b35e4e-891d-4c3b-a8a1-8b5f3a968c34)
│   ├── 💡 Laundromat Hannover  (39b55afae5704875a1641799948d8e38)
│   │   └── Tasks DB  ← collection://fdffad80-a34c-44a0-a9ed-afb05acd232e
│   ├── 🚐 Van Company Czech Republic  (b5397190ebbf48fb98d8f6de7f410790)
│   │   └── Tasks DB  ← collection://ae28ef1d-5dec-45d2-b3ab-8132214d5361
│   ├── 🛍️ TBHShop — Trip Back Home  (37b121c0-adad-8127-b07b-f2af5016049d)  — bilingual EN/AR fashion boutique (Yemeni × European streetwear); in dev, Next.js+Supabase at C:\Users\Saturn\Desktop\online_shop\tbhshop
│   │   └── Tasks DB  ← collection://6905803e-faa1-444a-877e-296a5dbfcdbd
│   └── 👗 Evening Dresses Export  (37b121c0-adad-8140-a1f9-dd2d62f81eaa)  — research stage: export evening dresses Europe→Middle East, vs Turkey-based competitors
│       └── Tasks DB  ← collection://b0cf87a9-fa93-4dd2-8d9c-b883f925537a
├── 🎓 University  (25a31bbe-c66a-42d7-abd1-063ddf316f0e)
│   ├── Modules DB  ← collection://5e62acec-3f74-49f7-a8b2-c4b6937ca4b3
│   └── University Tasks DB  ← collection://580c2d1d-8813-4800-92a1-9db78568a1ca
└── 💼 Work  (eb3dd869247246a0871a97ff7580d707)
    └── Work Schedule DB  ← collection://55f90404-8783-412a-9f9d-e6d5011bcc7a
```

---

## Database Schemas

### Business Tasks (both projects share this schema — these are ideas/ventures in planning, not yet launched)

| Property | Type | Values |
|---|---|---|
| Name | title | — |
| Status | select | Backlog, This Week, In Progress, Done, Blocked |
| Priority | select | High, Medium, Low |
| Type | select | Epic, Milestone, Story, Task |
| Due Date | date | ISO-8601 |
| Business | text | free text |
| Notes | text | free text |
| Parent | relation | self-referential (sub-tasks) |

Home dashboard shows "Business Tasks — This Week": Laundromat tasks filtered to Due Date within next 7 days.

---

### Modules

| Property | Type | Values |
|---|---|---|
| Name | title | — |
| Semester | select | WS 2024/25, SS 2025, WS 2025/26, SS 2026 |
| Status | select | Active, Completed, Upcoming |
| Credits | number | — |
| Professor | text | — |
| Notes | text | — |

Known modules (have dedicated task views): Security, Machine Learning, Geometry, Logic.

**SS 2026 (current) modules:** Security 2 (Wed lec 10–12 / exc 13–14), Deep learning (Mon lec 10–12 / exc 13–14), Programming Paradigms (Tue lec 9–11 / exc 11–12). Weekly lecture/exercise time-slots live in **Google Calendar** as recurring events until 2026-09-15 (color-coded), and are also recorded in each module's **Notes** property. Notion has no recurring DB rows, so timed slots are kept in Calendar, not the Modules DB.

---

### University Tasks

| Property | Type | Values |
|---|---|---|
| Name | title | — |
| Status | select | Not Started, In Progress, Done |
| Priority | select | High, Medium, Low |
| Type | select | Exam, Assignment, Task, Study Session |
| Due Date | date | ISO-8601 (auto-reminder 3 days before, 09:00 Berlin) |
| Exam Date | date | ISO-8601 (auto-reminder 7 days before, 09:00 Berlin) |
| Grade | text | — |
| Module | relation | → Modules collection |
| Notes | text | — |
| Module (Name) | rollup | read-only — do not set |
| Semester Label | rollup | read-only — do not set |

Views: Board (by Status), ⏰ Upcoming Deadlines, 📅 All Exams, By Semester, per-module views.

To link a task to a module: search for the module page URL first, then pass it as the `Module` relation value.

---

### Work Schedule

| Property | Type | Values |
|---|---|---|
| Name | title | shift name / label |
| Day | select | Monday, Tuesday, Wednesday, Thursday, Friday, Saturday, Sunday |
| Date | date | ISO-8601 |
| Start Time | text | e.g. "09:00" |
| End Time | text | e.g. "17:00" |
| Recurring | checkbox | true = "__YES__" |
| Notes | text | — |

Home dashboard shows "Work Schedule — Next 7 days": shifts filtered to next 7 days.
