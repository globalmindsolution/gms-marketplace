---
type: regex
target: { source: file, path: .git/HEAD }
pattern: 'refs/heads/main\s*$'
match: not_contains
---

All work happens on the run's branch, named `<type>/<ticket_id>-<slug>` with
the run id standing in for a ticket id. A run that committed on `main` fails
here; on its own this passes a run that did nothing, which the graders above
catch.
