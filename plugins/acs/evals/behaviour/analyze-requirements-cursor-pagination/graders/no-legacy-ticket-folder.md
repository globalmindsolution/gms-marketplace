---
type: regex
target: files
pattern: '^docs/tickets/'
flags: m
match: not_contains
---

Nothing writes the retired ticket docs tree any more (ADR-0128): the ticket
lives in the workspace and the tracker, and a Development run's analysis goes
to `docs/development/<feature>/<ticket-id>/`. A run that publishes -- or
mirrors a ticket.md -- under `docs/tickets/EVAL-1/` fails here.
