---
description: >-
  /acs:create-api-contract on a story whose surface is an EVENT, not an HTTP
  endpoint (order.shipped on the shop event bus), in a repo that already keeps
  machine-readable contracts as one JSON Schema per event under
  schemas/events/. The skill should resolve that contracts mode, publish api-
  contract.md specifying the event item (envelope and payload, at-least-once
  delivery) with no invented HTTP surface, add the new event's schema in the
  repo's existing convention, invent no docs/api/ tree, and close with outcome
  contract_written.
expected_outcome: >-
  docs/tickets/EVAL-1/api-contract.md exists with a Surface item for
  order.shipped naming event_id and no HTTP-verb item, its Contract files
  section naming schemas/events/; a new schemas/events/*shipped*.json was
  created and no docs/api/ file; run.json records the step completed with
  outcome contract_written.
tags: [behaviour]
max_turns: 100
timeout_seconds: 1800
allowed_tools: [Read, Glob, Grep, Skill, Bash, Write, Edit, Agent]
---

Run the /acs:create-api-contract skill for ticket EVAL-1 (publish
order.shipped when an order ships). The analysis and the implementation plan
are already published in the ticket's docs folder, uncommitted, on main. Take
the skill all the way through: contract published to the ticket's docs folder
and left uncommitted (no branch, no commit: /acs:create-pr commits later), and
the step finished.

I can't answer questions during this run, so don't ask me anything. The
decisions are settled: the event is named order.shipped and uses the same
envelope as order.created (event_id, occurred_at, schema_version 1); its
payload is order_id, carrier, tracking_number and shipped_at; delivery is
at-least-once and consumers deduplicate by event_id. There is no HTTP
endpoint in this ticket. Follow the way this repo already specifies its
events.
