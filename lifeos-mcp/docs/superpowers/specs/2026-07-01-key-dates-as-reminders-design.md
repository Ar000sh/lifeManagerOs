# Key Dates as Reminders — Design

**Date:** 2026-07-01
**Branch:** `feat/dynamic-skills`
**Scope:** A refinement to the already-shipped dynamic task/record schema
(`docs/superpowers/specs/2026-06-29-dynamic-task-schema-design.md`). It fixes the
*meaning* of highlighted dates ("key dates") and tightens when `/today` surfaces them.
No schema, model, or write-path changes.

## Problem

The dynamic schema introduced `highlight: true` date fields ("key dates") — e.g. an
"Exam Date" on a university task, distinct from the task's own `due_date`. Two things
were left implicit, and we got the semantics wrong by assumption:

1. **What is a highlighted date for?** It was treated as a passive reference that could
   in principle become a missed/overdue concern. That conflates it with `due_date`.
2. **When should it surface in `/today`?** The current code surfaces every highlighted
   date from today onward (`kv >= today`), so a date three weeks out appears in `/today`
   every single day until it arrives.

## Decisions (from brainstorming)

- **A highlighted date is a *reminder*, not a deadline.** It nudges you that a checkpoint
  is here; it carries no deadline weight.
- **No nagging, ever.** A reminder never becomes "missed" or overdue. There is no opt-in
  nag flag. If something genuinely needs a deadline, it becomes a **task** with its own
  `due_date`.
- **`due_date` is the sole deadline mechanism.** It alone drives whether a task appears in
  `/today` and whether it is flagged `overdue`. This is unchanged from today.
- **`/today` surfaces a reminder only on its exact date** (`kv == today`). Lead-time
  option (c) from brainstorming: minimal, show-on-the-day. Chosen "for now"; a rolling
  window can be revisited later.
- **A non-highlighted date is a plain field** — carried on the record, never surfaced by
  date.
- **The section keeps its name, "Key dates."** The rendered line uses label-first
  Format 1.

## Behavior

### Read / surfacing

- **`get_today`** (`_task_rows`): for each highlighted date field, surface a reminder
  **iff the date equals today** (`kv == today`). Past and future highlighted dates are
  not surfaced. The date value is still carried inline in `record.fields[...]` regardless
  (the existing fields/key-dates duplication is unchanged).
- **`get_week`**: unchanged. Each highlighted date in the current week buckets onto its
  own day (`start <= kv <= end`). Because the week view is inherently day-by-day, this
  already matches the "show on the day" rule.
- **`due_date`** continues to drive task surfacing (`due <= today` in `/today`; within the
  week in `/week`) and the `overdue = due < today` flag. Reminders never affect this.

### Reminder lifecycle (illustrative)

Task "Launch feature", `due_date` Aug 8, highlighted "Contact Designer" Jul 15.

| Day | `/today` task list | `/today` Key dates |
|-----|--------------------|--------------------|
| Jul 14 | — (not due) | — (not yet) |
| Jul 15 | — (not due) | • Contact Designer — Launch feature |
| Jul 16 | — (not due) | — (past, dropped, no nag) |
| Aug 8  | ▸ Launch feature (due today) | — |

## Tool output (unchanged shape)

Each surfaced reminder emits `{title, label, date}`, where `label` is the Notion column
name verbatim (e.g. `"Contact Designer"`, `"Exam Date"`). No new fields are added. The
reminder is nested under its area block, so area context is implicit.

## Formatter (Phase B — documented, not built here)

The `/today` and `/week` skills render the reminders the tool emits. The section keeps the
name **"Key dates"** and uses **Format 1** (label first):

```
📌 Key dates
  • Contact Designer — Launch feature
  • Exam Date — Revise for ML exam
```

- The text is the column label verbatim — naming columns well (`Contact Designer`, not
  `Date 2`) is what makes reminders read nicely; the tool performs no transformation.
- A highlighted date should be rendered **only** in the Key dates section, **not** also
  re-printed inline among the task's fields (avoid the known fields/key-dates duplication).
- In `/week`, the same line appears under its day rather than a "today" section.

## Code impact

- **`lifeos_mcp/tools/get_today.py`** (`_task_rows`): change the key-date gate from
  `kv and kv >= today` to `kv and kv == today`. One line.
- **Tests:** update the `/today` tests that currently assume a *future* highlighted date
  surfaces (they encode the old "every day until" behavior) so their highlighted dates
  equal the run date. Affected tests live in `tests/test_tools_today.py` and
  `tests/test_edgecases_review.py`. Add/keep an explicit case proving a future highlighted
  date does **not** surface in `/today` and a same-day one does.
- **No changes** to `get_week.py`, schema accessors, models, `build_props`/`extract_props`,
  or `add_record`.

## Testing

- *Exact-day surfacing:* a highlighted date equal to the run date surfaces in `/today`;
  a future one does not; a past one does not.
- *Inline retention:* the highlighted date value remains in `record.fields[...]` even when
  not surfaced.
- *No deadline weight:* a task whose only in-range date is a (non-today) highlighted date
  does not appear in the `/today` task list and is never flagged `overdue` from it.
- *Week unchanged:* existing `get_week` key-date bucketing tests stay green.

## Out of scope / deferred

- Rolling-window or N-days-ahead lead time for reminders (option (b)) — revisit later.
- Any nag/missed-reminder behavior — explicitly rejected.
- The Phase-B formatter implementation of `/today` `/week` (this spec only fixes the
  rendering convention).
