---
description: >-
  /acs:analyze-requirements on a story that is design-significant (a new
  inbound integration with two carriers, a new stored shape, an outbound email
  flow) but was minted with needs_design false. The survey should recommend a
  design, and because the prompt confirms any design recommendation up front,
  the skill records that answer in the ledger and applies needs_design true to
  the ticket through `acs.py ticket save`, publishing the analysis with
  needs_design_recommendation true.
expected_outcome: >-
  The ticket's ticket.json now has needs_design true;
  docs/tickets/EVAL-1/analysis.md has needs_design_recommendation true in its
  front matter; the clarification ledger holds a design question from analyze-
  requirements; the step's state.json records the run completed.
tags: [behaviour]
max_turns: 100
timeout_seconds: 1800
allowed_tools: [Read, Glob, Grep, Skill, Bash, Write, Edit, Agent]
---

Run the /acs:analyze-requirements skill for ticket EVAL-1 (live order tracking
from carrier updates) and take it all the way through: survey, analysis
published to the ticket's docs folder and left uncommitted (no branch, no
commit: /acs:create-pr commits later), and the step finished.

I can't answer questions during this run, so here are my answers — record
them as answered, don't ask me anything:

- Both carriers push status changes to us as signed webhooks (a shared secret
  per carrier); we never poll them.
- The statuses are label_created, in_transit, out_for_delivery, delivered and
  exception.
- Emails go through a transactional email provider we have not chosen yet;
  treat it as an outbound HTTP API.
- If your analysis recommends a design for this ticket, I confirm it: set
  needs_design on the ticket. The three acceptance criteria are confirmed as
  written.
