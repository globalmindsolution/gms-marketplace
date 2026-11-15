---
description: >-
  /acs:audit-security on a small Flask service with an unauthenticated SQL
  injection (GET /orders/search puts the `q` query parameter into an f-string
  that cursor.execute runs unbound), a hard-coded payments API token in
  config/production.ini, and a requirements.txt nothing can scan (no scanner
  in the repo, no network). It should confirm both findings -- the injection
  at critical or high with CWE-89, the token named by location, kind and a
  redacted form and never by value -- state the dependencies as uncovered
  rather than clean, skip the threat model (no architecture set), write the
  report from the template so the post-hook derives the counts, and change
  nothing, ticket nothing.
expected_outcome: >-
  steps/audit-security/iter-1/report.md has every template section in order,
  the injection under Critical or High with CWE-89 and orders_api.py, the
  token in config/production.ini under a severity; the token's value is in
  neither the report, result.json nor the reply; Scope and coverage says the
  dependencies are uncovered and no line calls them clean or names a CVE; the
  post-hook accepted the result and counted states.audit from the report;
  src/shop/orders_api.py, config/production.ini and requirements.txt are byte
  for byte as committed; no file created under docs/, config/, src/ or tests/;
  no ticket.
tags: [behaviour]
max_turns: 120
timeout_seconds: 2400
allowed_tools: [Read, Glob, Grep, Skill, Bash, Write, Edit, Agent]
---

Run the /acs:audit-security skill on the whole repository, all categories. A
run for this audit is already open on this checkout. Report what it confirms,
worst first. Don't fix anything, don't change any file in the repo, don't
install anything, and don't create tickets. Don't ask me anything.
