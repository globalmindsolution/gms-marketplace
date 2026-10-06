---
description: >-
  /acs:analyze-requirements on a story whose change is architecturally heavy
  (a new inbound integration with two carriers, a new stored shape, an
  outbound email flow). Since ADR-0139 the analysis says nothing about design:
  it maps the impact and names the risks, but records no
  needs_design_recommendation, asks no design question, writes no design flag
  into the run's requirements or the ticket, and does not point the user at
  /acs:create-tech-design.
expected_outcome: >-
  docs/development/order-tracking/EVAL-1/analysis/README.md exists with no
  needs_design_recommendation key; the run's requirements.md and the ticket's
  ticket.json carry no needs_design; the clarification ledger holds no
  question asking whether a design is needed; the final reply does not name
  /acs:create-tech-design; the step's state.json records the run completed.
tags: [behaviour]
max_turns: 100
timeout_seconds: 1800
allowed_tools: [Read, Glob, Grep, Skill, Bash, Write, Edit, Agent]
---

Run the /acs:analyze-requirements skill for ticket EVAL-1 (live order tracking
from carrier updates) and take it all the way through: survey, analysis
published to the run's development folder and left uncommitted (no branch, no
commit: /acs:create-pr commits later), and the step finished.

I can't answer questions during this run, so here are my answers — record
them as answered, don't ask me anything:

- Both carriers push status changes to us as signed webhooks (a shared secret
  per carrier); we never poll them.
- The statuses are label_created, in_transit, out_for_delivery, delivered and
  exception.
- Emails go through a transactional email provider we have not chosen yet;
  treat it as an outbound HTTP API.
- The three acceptance criteria are confirmed as written.
