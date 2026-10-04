---
description: >-
  /acs:audit-security on a repo with nothing exploitable and no threat model:
  src/shop/stats.py builds queries with f-strings that interpolate only a
  module constant (the one input is bound), and docs/architecture holds an HLD
  with no hld/data-flow.md or hld/cross-cutting.md. A candidate raised on the
  look-alike is refuted and goes under Refuted, never at a severity; the
  threat-model slice is skipped with the reason naming the data-flow view and
  /acs:setup; the report still follows the template, and nothing is changed.
expected_outcome: >-
  steps/audit-security/iter-1/report.md has every template section in order,
  nothing about stats.py under Critical, High, Medium or Low, and Scope and
  coverage marks the threat model skipped with data-flow or /acs:setup as the
  reason; the post-hook accepted the result and its states.audit counts 0 at
  every severity with threat-model in skipped; src/shop/stats.py is byte for
  byte as committed; nothing created under docs/, src/ or tests/; no ticket.
tags: [behaviour]
max_turns: 120
timeout_seconds: 2400
allowed_tools: [Read, Glob, Grep, Skill, Bash, Write, Edit, Agent]
---

Run the /acs:audit-security skill over the whole repository, every category
including the threat model if there is one. A run for this audit is already
open on this checkout. Tell me what it confirms and what it ruled out. Don't
change any file, don't install anything, and don't create tickets. Don't ask
me anything.
