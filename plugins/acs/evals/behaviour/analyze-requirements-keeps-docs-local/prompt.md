---
description: >-
  /acs:analyze-requirements in a repo whose team saved "keep run documents
  local" (docs.share_run_documents false in .acs/settings.json). The skill
  should follow the saved default silently: the analysis goes to the run's
  state folder (steps/analyze-requirements/local/analysis/), nothing is
  written under docs/, the choice is neither asked nor re-saved, and the
  completion report says the analysis was kept local.
expected_outcome: >-
  .acs/state-machine/example-shop/runs/EVAL-1/steps/analyze-requirements/local/analysis/README.md
  exists with api_surface true, and its customer-listing.md beside it has an
  impact map naming src/shop/__init__.py;
  no file was created under docs/; .acs/settings.json still records
  share_run_documents false and no .acs/settings.local.json was created; the
  result's files name no docs/ path; the reply says the analysis was kept
  local; the step's state.json records the run completed.
tags: [behaviour]
max_turns: 100
timeout_seconds: 1800
allowed_tools: [Read, Glob, Grep, Skill, Bash, Write, Edit, Agent]
---

Run the /acs:analyze-requirements skill for ticket EVAL-1 (cursor pagination
for GET /customers) and take it all the way through: survey, analysis
written, and the step finished.

I can't answer questions during this run, so here are the answers to anything
you would ask me — record them as answered, don't ask me anything:

- The cursor is opaque to clients: a URL-safe base64 encoding of the last
  customer id on the page.
- `offset` keeps working for existing clients (deprecated, not removed);
  `cursor` wins when both are given.
- `limit` keeps its default of 20; the maximum is 100.
- A malformed or tampered cursor returns HTTP 400 with error code
  `invalid_cursor`.
- The analysis covers one bounded context, the customer listing — file it as
  `customer-listing.md`.
- This does not need a design. The three acceptance criteria on the ticket are
  confirmed as written; if you propose a refinement, record it as a proposal
  rather than applying it.
