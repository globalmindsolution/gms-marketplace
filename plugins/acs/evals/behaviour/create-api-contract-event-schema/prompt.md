---
description: >-
  /acs:create-api-contract as a Design skill on a story whose surface is an
  EVENT, not an HTTP endpoint (order.shipped on the shop event bus), with
  no plan, in a repo that keeps one JSON Schema per event under
  schemas/events/ and documents its order events in
  lld/order-tracking/api/order-events.md. The skill should revise that
  interface document in place -- an order.shipped item with its envelope
  and payload, at-least-once delivery -- bump it to proposed v2, publish the
  run record, invent no HTTP surface, and write documents only: no new JSON
  Schema (the plan and /acs:code write that later), no docs/api/ tree.
expected_outcome: >-
  docs/architecture/lld/order-tracking/api/order-events.md carries status
  proposed, version 2, tickets EVAL-1 and an order.shipped item naming
  event_id, with no HTTP-verb item; the run record
  docs/architecture/lld/order-tracking/EVAL-1/api-contract.md exists; no
  file under schemas/ or docs/api/ was created and
  schemas/events/order.created.json is unchanged; the step's result.json
  carries outcome contract_written and its state.json is completed.
tags: [behaviour]
max_turns: 150
timeout_seconds: 2400
allowed_tools: [Read, Glob, Grep, Skill, Bash, Write, Edit, Agent]
---

Run the /acs:create-api-contract skill for ticket EVAL-1 (publish
order.shipped when an order ships), feature order-tracking. Its analysis is
already published; there is no implementation plan yet -- the event is
designed first. Take the skill all the way through: designed, reviewed, the
run record published and the step finished, everything left uncommitted on
main.

I can't answer questions during this run, so don't ask me anything. The
decisions are settled: the event is named order.shipped and uses the same
envelope as order.created (event_id, occurred_at, schema_version 1); its
payload is order_id, carrier, tracking_number and shipped_at; delivery is
at-least-once and consumers deduplicate by event_id. There is no HTTP
endpoint in this ticket. Keep the run documents in the repo, as the team
setting says.
