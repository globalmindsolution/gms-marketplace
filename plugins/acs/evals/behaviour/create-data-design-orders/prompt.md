---
description: >-
  /acs:create-data-design on a story (EVAL-1, feature orders) that adds
  persisted data -- orders and their lines -- to a repo whose HLD carries
  the conceptual data model and the data conventions, with both data types
  enabled by default. It should write the feature's logical ERD and
  physical schema, each with version front matter (proposed: nothing is
  built), Mermaid erDiagrams and a prose migration outline, under
  lld/orders/data/ only; write no migration or code; record every written
  path in states.files; and finish through its post-hook -- without asking
  anything.
expected_outcome: >-
  docs/architecture/lld/orders/data/logical-erd.md and physical-schema.md
  exist with front matter status proposed, ticket EVAL-1, feature orders,
  their required sections in order and an erDiagram each; the physical
  schema indexes customer_id and its migration outline holds no DDL; no
  migration, .py or .sql file and no document outside lld/orders/ (bar the
  feature README) was created; hld/data-model.md is unchanged; the step's
  state.json is completed and its states.files lists both documents.
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
