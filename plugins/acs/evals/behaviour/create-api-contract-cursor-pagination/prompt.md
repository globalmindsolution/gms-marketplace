---
description: >-
  /acs:create-api-contract on a planned story whose plan owes an API contract
  (GET /customers gains cursor, next_cursor and invalid_cursor). The repo keeps
  no machine-readable contracts, so the skill should publish api-contract.md
  alone -- front matter, the seven sections, the GET /customers item and the
  invalid_cursor error -- invent no docs/api/ tree, and close its step with
  outcome contract_written, without asking anything.
expected_outcome: >-
  docs/tickets/EVAL-1/api-contract.md exists with items >= 1, the seven
  headings in order, a Surface item for GET /customers carrying next_cursor
  and invalid_cursor in the Error model; no docs/api/ or OpenAPI file was
  created; the run's run.json records the step completed with outcome
  contract_written.
tags: [behaviour]
max_turns: 100
timeout_seconds: 1800
allowed_tools: [Read, Glob, Grep, Skill, Bash, Write, Edit, Agent]
---

Run the /acs:create-api-contract skill for ticket EVAL-1 (cursor pagination
for GET /customers). The analysis and the implementation plan are already
published in the ticket's docs folder, uncommitted, on main. Take the skill
all the way through: contract published to the ticket's docs folder and left
uncommitted (no branch, no commit: /acs:create-pr commits later), and the step
finished.

I can't answer questions during this run, so don't ask me anything. The
compatibility decisions are settled: the change is backward compatible and in
place, no new API version; `offset` stays supported (deprecated) and `cursor`
wins when both are given; the cursor is an opaque string; a malformed cursor
is HTTP 400 with error code `invalid_cursor`. This repo does not keep
OpenAPI or any other machine-readable contract, and I don't want one
introduced in this ticket.
