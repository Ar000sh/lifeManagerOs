FIXTURE_MAP = {
    "workspace_root": "ws-root",
    "anchors": {
        "business_root": "biz-root",
        "university_tasks_db": "uni-tasks",
        "modules_db": "mod-db",
        "work_schedule_db": "work-db",
    },
    "areas": {
        "ventures": {"label": "Business", "emoji": "🚀",
                     "group": {"under": "business_root", "child_sources": [{"role": "tasks"}]}},
        "university": {"label": "University", "emoji": "🎓",
                       "sources": [{"anchor": "university_tasks_db", "role": "tasks"}],
                       "catalog": {"anchor": "modules_db", "role": "catalog"}},
        "work": {"label": "Work", "emoji": "💼",
                 "sources": [{"anchor": "work_schedule_db", "role": "schedule"}]},
    },
    "role_schemas": {
        "university_tasks_db": {"role": "tasks", "title": "Name", "status": "Status",
                                "priority": "Priority", "due_date": "Due Date",
                                "exam_date": "Exam Date", "catalog_rel": "Module",
                                "status_values": {"done": "Done", "this_week": "This Week"}},
        "work_schedule_db": {"role": "schedule", "title": "Name", "date": "Date",
                             "start": "Start Time", "end": "End Time"},
        "modules_db": {"role": "catalog", "title": "Name", "semester": "Semester"},
    },
    "child_schema_defaults": {
        "tasks": {"title": "Name", "status": "Status", "priority": "Priority",
                  "due_date": "Due Date",
                  "status_values": {"done": "Done", "this_week": "This Week"}},
    },
    "resolved": {
        "groups": {"ventures": {
            "laundro-page": {"label": "Laundromat Hannover", "role": "tasks",
                             "tasks_db": "laundro-db", "cached_at": "2026-06-26"}}},
        "tombstones": {}, "ignored": [],
    },
}

ALT_MAP = {
  "workspace_root": "alt-root",
  "anchors": {"client_root": "client-root", "todo_db": "todo-db"},
  "areas": {
    "clients": {"label": "Clients", "emoji": "🧾",
                "group": {"under": "client-root", "child_sources": [{"role": "tasks"}]}},
    "personal": {"label": "Persönlich", "emoji": "🏠",
                 "sources": [{"anchor": "todo_db", "role": "tasks"}]}
  },
  "role_schemas": {
    "todo_db": {"role": "tasks", "title": "Titel", "due_date": "Fällig",
                "done_when": {"property": "Erledigt", "equals": True}}
  },
  "child_schema_defaults": {
    "tasks": {"title": "Name", "due_date": "Due", "status": "Status",
              "status_values": {"done": "Done"}}
  },
  "resolved": {"groups": {"clients": {}}, "tombstones": {}, "ignored": []}
}
