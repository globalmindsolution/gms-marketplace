---
description: >-
  /acs:analyze-requirements on a seeded story (cursor pagination for GET
  /customers) with every clarification answered up front. The skill should
  survey the code, publish analysis.md to the ticket's docs folder with its
  machine-read front matter and seven sections, left uncommitted on main, and
  close its step through the post-hook -- without asking anything.
expected_outcome: >-
  docs/tickets/EVAL-1/analysis.md exists with ticket EVAL-1, api_surface true
  and the seven headings in order, its impact map names src/shop/__init__.py,
  main is still checked out with nothing committed, and the step's state.json
  records the run completed.
tags: [behaviour]
max_turns: 100
timeout_seconds: 1800
allowed_tools: [Read, Glob, Grep, Skill, Bash, Write, Edit, Agent]
---

Run the /acs:analyze-requirements skill for ticket EVAL-1 (cursor pagination
for GET /customers) and take it all the way through: survey, analysis
published to the ticket's docs folder and left uncommitted (no branch, no
commit: /acs:create-pr commits later), and the step finished.

I can't answer questions during this run, so here are the answers to anything
you would ask me — record them as answered, don't ask me anything:

- The cursor is opaque to clients: a URL-safe base64 encoding of the last
  customer id on the page.
- `offset` keeps working for existing clients (deprecated, not removed);
  `cursor` wins when both are given.
- `limit` keeps its default of 20; the maximum is 100.
- A malformed or tampered cursor returns HTTP 400 with error code
  `invalid_cursor`.
- This does not need a design. The three acceptance criteria on the ticket are
  confirmed as written; if you propose a refinement, record it as a proposal
  rather than applying it.
