---
description: >-
  A raw request with no ticket, shipped with one command: cap the customer
  page size at 100. ship starts a run over the request (a free-text subject)
  and drives workflows/ship.yaml from its cursor -- the cap implemented
  (uncommitted until create-pr) and reviewed -- until create-pr fails at its
  critical gh base detection before any push. ship stops there, reports it,
  and never merges.
expected_outcome: >-
  A run's steps/review-code/verdict.json and steps/create-pr/state.json
  exist; src/shop/__init__.py enforces a cap of 100; nothing reached the local
  origin; no gh pr merge was run; the reply surfaces the gh failure.
tags: [behaviour]
max_turns: 200
timeout_seconds: 3600
allowed_tools: [Read, Glob, Grep, Skill, Bash, Write, Edit, Agent]
---

Use the /acs:ship skill to ship this change end to end, up to its pull
request — there is no ticket for it yet: "Cap the customer page size at 100.
list_customers must refuse a limit above 100 with a ValueError naming the
maximum; a limit of exactly 100 is still served, and the default page size
stays 20." Where a step would ask me something, decide it yourself and record
it as an assumption. Do not ask me anything; I will not be able to answer.
