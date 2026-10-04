---
description: >-
  /acs:create-design on a design-flagged story (checkout with card payments
  through the external payments gateway) with the open decisions answered up
  front. The skill should publish design.md to the ticket's docs folder with
  the six required sections, at least two weighed options, a Mermaid flow and
  an architecture-conformance call, write no code, and close its step --
  without asking anything.
expected_outcome: >-
  docs/architecture/lld/checkout-with-card-payments/EVAL-1/design.md exists with the six headings in order, two or
  more ### options under Options considered, a mermaid block and an
  Architecture conformance subsection under Architecture; nothing under src/
  or tests/ was created; the step's state.json records the run completed.
tags: [behaviour]
max_turns: 120
timeout_seconds: 1800
allowed_tools: [Read, Glob, Grep, Skill, Bash, Write, Edit, Agent]
---

Run the /acs:create-design skill for ticket EVAL-1 (checkout with card
payments). Take it all the way through: the design reviewed, published to the
ticket's docs folder, and the step finished.

I can't answer questions during this run, so here are my answers to the open
decisions — record them as answered, don't ask me anything:

- Prefer the simplest option that meets the PRD's p95 < 300 ms at today's
  volume; I'd rather not add a queue or a new service yet unless the options
  analysis shows it's necessary.
- Card data must never touch our servers: we only ever handle the gateway's
  card token.
- Declined cards return HTTP 402 with `card_declined`; retries use an
  idempotency key supplied by the client.
- No feature flag is needed; a plain deploy with redeploy-to-roll-back is fine.
