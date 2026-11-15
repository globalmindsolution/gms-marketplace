---
description: >-
  /acs:create-data-design on a PRD feature slug (orders) with NO ticket: the
  requirements arrive as the invocation's slug and prompt, which the run
  records in its requirements.md (ADR-0128 -- no skill requires a ticket). It
  should take the feature from the argument, write the feature's logical ERD
  and physical schema under lld/orders/data/, versioned with no ticket
  (`tickets: []`, feature orders, proposed), with Mermaid erDiagrams and a
  prose migration outline; write no migration or code; mint no ticket and ask
  for none; and finish through its post-hook -- without asking anything.
expected_outcome: >-
  docs/architecture/lld/orders/data/logical-erd.md and physical-schema.md
  exist, each opening with front matter status proposed, tickets [] and
  feature orders, their required sections in order and an erDiagram each; the
  physical schema indexes customer_id; no ticket was minted; no migration,
  .py or .sql file and no document outside lld/orders/ (bar the feature
  README) was created; the run's create-data-design result.json exists and
  nothing was committed.
tags: [behaviour]
max_turns: 150
timeout_seconds: 2400
allowed_tools: [Read, Glob, Grep, Skill, Bash, Write, Edit, Agent]
---

Run the /acs:create-data-design skill with arguments `orders "Shoppers order
one or more products in a single order: each order line records the product,
the quantity and the unit price at the time of ordering; an order belongs to
exactly one customer and records its status (placed, paid, shipped or
delivered) and its total in cents; a shopper lists their own orders newest
first, 20 per page."` -- there is no ticket for this and I don't want one:
design the data of PRD feature F4 (orders) from these requirements. Take it all
the way through: surveyed, written, reviewed, and the step finished.

I can't answer questions during this run, so here are my answers to the open
decisions -- record them as answered, don't ask me anything:
- Keys follow hld/cross-cutting.md: a BIGINT identity `id` per table.
- The price an order was placed at is copied onto each order line, in cents.
- The order status is a text column with a check constraint; no soft delete.
