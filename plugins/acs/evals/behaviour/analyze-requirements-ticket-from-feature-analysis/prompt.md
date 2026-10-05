---
description: >-
  /acs:analyze-requirements on a delivery ticket (EVAL-1, cursor pagination)
  whose PRD feature, customer-listing, already has a living analysis from
  Discovery. A ticket run is a Development run: the survey starts from the
  feature's analysis -- the only place the decided maximum page size (250) is
  recorded -- and the run publishes its OWN analysis to
  the folder docs/development/customer-listing/EVAL-1/analysis/, leaving the living
  analysis untouched and writing nothing under docs/tickets/.
expected_outcome: >-
  docs/development/customer-listing/EVAL-1/analysis/README.md exists with ticket
  EVAL-1 in its front matter and the page-size maximum 250; the feature's
  living analysis is still version 1; nothing was created under docs/tickets/;
  the step's state.json records the run completed; main is still checked out
  with nothing committed.
tags: [behaviour]
max_turns: 100
timeout_seconds: 1800
allowed_tools: [Read, Glob, Grep, Skill, Bash, Write, Edit, Agent]
---

Run the /acs:analyze-requirements skill for ticket EVAL-1 (cursor pagination
for GET /customers) and take it all the way through: survey, the analysis
published and left uncommitted (no branch, no commit: /acs:create-pr commits
later), and the step finished.

We already analyzed the customer listing feature in discovery, and every
answer recorded there still stands; I have nothing to add or change. I can't
answer questions during this run, so don't ask me anything. The ticket does
not need a design, and its three acceptance criteria stand as written.
