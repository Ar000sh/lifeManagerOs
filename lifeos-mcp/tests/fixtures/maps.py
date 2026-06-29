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
        "university_tasks_db": {
            "role": "tasks",
            "title": {"col": "Name", "type": "title"},
            "due_date": {"col": "Due Date", "type": "date"},
            "done_predicate": {"col": "Status", "type": "status", "equals": "Done"},
            "week_predicate": {"col": "Status", "equals": "This Week"},
            "fields": {
                "status": {"col": "Status", "type": "status"},
                "priority": {"col": "Priority", "type": "select"},
                "exam_date": {"col": "Exam Date", "type": "date", "highlight": True},
                "module": {"col": "Module", "type": "relation"},
            },
        },
        "work_schedule_db": {
            "role": "schedule",
            "title": {"col": "Name", "type": "title"},
            "date": {"col": "Date", "type": "date"},
            "start": {"col": "Start Time", "type": "rich_text"},
            "end": {"col": "End Time", "type": "rich_text"},
            "fields": {},
        },
        "modules_db": {
            "role": "catalog",
            "title": {"col": "Name", "type": "title"},
            "fields": {"semester": {"col": "Semester", "type": "rich_text"}},
        },
    },
    "child_schema_defaults": {
        "tasks": {
            "role": "tasks",
            "title": {"col": "Name", "type": "title"},
            "due_date": {"col": "Due Date", "type": "date"},
            "done_predicate": {"col": "Status", "type": "status", "equals": "Done"},
            "week_predicate": {"col": "Status", "equals": "This Week"},
            "fields": {
                "status": {"col": "Status", "type": "status"},
                "priority": {"col": "Priority", "type": "select"},
            },
        },
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
                     "sources": [{"anchor": "todo_db", "role": "tasks"}]},
    },
    "role_schemas": {
        "todo_db": {
            "role": "tasks",
            "title": {"col": "Titel", "type": "title"},
            "due_date": {"col": "Fällig", "type": "date"},
            "done_predicate": {"col": "Erledigt", "type": "checkbox", "equals": True},
            "fields": {},
        },
    },
    "child_schema_defaults": {
        "tasks": {
            "role": "tasks",
            "title": {"col": "Name", "type": "title"},
            "due_date": {"col": "Due", "type": "date"},
            "done_predicate": {"col": "Status", "type": "status", "equals": "Done"},
            "fields": {"status": {"col": "Status", "type": "status"}},
        },
    },
    "resolved": {"groups": {"clients": {}}, "tombstones": {}, "ignored": []},
}
