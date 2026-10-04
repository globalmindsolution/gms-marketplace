---
description: >-
  /acs:create-data-design on the orders story (EVAL-1) in a repo whose
  design.lld_types keeps the logical ERD and drops physical-schema; the
  request does not mention the setting. It should write the logical ERD
  alone under lld/orders/data/, with version front matter and an
  erDiagram, never the disabled physical schema (not as its own file, not
  folded into the ERD), record types ["logical-erd"] and the written paths
  in states.files, and say why the physical schema is absent.
expected_outcome: >-
  docs/architecture/lld/orders/data/logical-erd.md exists, versioned
  proposed for EVAL-1 and feature orders, with its four sections and an
  erDiagram and no column types or migration outline; physical-schema.md
  does not exist; no other document, migration or code is created; the
  step's state.json is completed with types exactly ["logical-erd"] and the
  ERD in states.files.
tags: [behaviour]
max_turns: 150
timeout_seconds: 2400
allowed_tools: [Read, Glob, Grep, Skill, Bash, Write, Edit, Agent]
---

Run the /acs:create-data-design skill for ticket EVAL-1, feature orders. Take
it all the way through: surveyed, written, reviewed, and the step finished.

I can't answer questions during this run, so here are my answers to the open
decisions -- record them as answered, don't ask me anything:
- Keys follow hld/cross-cutting.md: a BIGINT identity `id` per table.
- The price an order was placed at is copied onto each order line, in cents.
- The order status is a text column with a check constraint; no soft delete.
