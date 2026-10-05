---
description: >-
  /acs:create-api-contract on the cursor-pagination story (EVAL-1) in a
  repo whose design.lld_types drops api-contract; the request does not
  mention the setting. The skill owns that one LLD type, so it should
  complete as a recorded no-op -- result.json completed with outcome
  type_disabled and empty states, through the post-hook -- write no
  interface document, run record, machine-readable contract or code, and
  say why nothing was written.
expected_outcome: >-
  The step's result.json carries outcome type_disabled and its state.json is
  completed; no file under docs/, schemas/ or src/ was created and
  docs/architecture/lld/customer-listing/api/customers.md is unchanged
  (implemented v1); the final reply says the api-contract type is disabled
  in design.lld_types.
tags: [behaviour]
max_turns: 60
timeout_seconds: 1200
allowed_tools: [Read, Glob, Grep, Skill, Bash, Write, Edit, Agent]
---

Run the /acs:create-api-contract skill for ticket EVAL-1 (cursor pagination
for GET /customers), feature customer-listing, and take it all the way to
the step finished.

I can't answer questions during this run, so don't ask me anything. If it
turns out this skill has nothing to write for this repo, don't write
anything -- just tell me what it recorded and why.
