---
description: >-
  /acs:create-api-contract as a Design skill on a story (EVAL-1, feature
  customer-listing) whose approved analysis names an interface change and
  which has NO plan. The feature's interface is already documented
  (lld/customer-listing/api/customers.md, implemented v1). It should revise
  that document in place -- GET /customers gains cursor and next_cursor,
  invalid_cursor joins the Error model -- bump it to proposed v2 through
  acs.py design, publish the run record api-contract.md linking it, write no
  machine-readable contract and no code, and close with outcome
  contract_written -- without asking anything.
expected_outcome: >-
  docs/architecture/lld/customer-listing/api/customers.md carries front
  matter status proposed, version 2, tickets EVAL-1, its six headings in
  order, a GET /customers item naming next_cursor and invalid_cursor in its
  Error model; docs/architecture/lld/customer-listing/EVAL-1/api-contract.md
  exists with items >= 1, interfaces naming customers.md and its five
  headings; no docs/api/, OpenAPI file, source or test was written; the
  step's result.json carries outcome contract_written and its state.json is
  completed with both documents in states.files.
tags: [behaviour]
max_turns: 150
timeout_seconds: 2400
allowed_tools: [Read, Glob, Grep, Skill, Bash, Write, Edit, Agent]
---

Run the /acs:create-api-contract skill for ticket EVAL-1 (cursor pagination
for GET /customers), feature customer-listing. Its analysis is already
published; there is no implementation plan yet -- the API is designed first.
Take the skill all the way through: designed, reviewed, the run record
published and the step finished, everything left uncommitted on main.

I can't answer questions during this run, so here are my answers to the
open decisions -- record them as answered, don't ask me anything:
- The change is backward compatible and in place: no new API version.
- `offset` stays supported but deprecated; when both are given, `cursor` wins.
- The cursor is an opaque string; a malformed one is HTTP 400 with error code
  `invalid_cursor`.
- Keep the run documents in the repo, as the team setting says.
This repo keeps no OpenAPI or other machine-readable contract, and none is
wanted.
