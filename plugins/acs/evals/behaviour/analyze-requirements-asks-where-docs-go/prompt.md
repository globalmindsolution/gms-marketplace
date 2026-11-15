---
description: >-
  /acs:analyze-requirements on the first acs run in a repo with no docs folder
  and no saved document choice. `docs where` reports that both the share choice
  and the Development folder need the user's answer; the prompt relays them (share
  with the team, in docs/changes). The skill should save both with `acs.py docs
  decide` -- the team scope, merged into .acs/settings.json -- and publish the
  analysis into the folder the user chose, never into the built-in default.
expected_outcome: >-
  .acs/settings.json still names ticket prefix EVAL and now records
  docs.share_run_documents true and docs.development_dir docs/changes; no
  .acs/settings.local.json was created; docs/changes/customer-listing/EVAL-1/analysis/README.md
  exists and is recorded in the result's files; nothing was written under
  docs/development/; the step's state.json records the run completed.
tags: [behaviour]
max_turns: 100
timeout_seconds: 1800
allowed_tools: [Read, Glob, Grep, Skill, Bash, Write, Edit, Agent]
---

Run the /acs:analyze-requirements skill for ticket EVAL-1 (cursor pagination
for GET /customers) and take it all the way through: survey, analysis
written, and the step finished (no branch, no commit: /acs:create-pr commits
later).

This is the first time acs runs in this repo, so it has never been told where
documents go. I can't answer questions during this run, so here are the
answers to anything you would ask me — record them as answered, don't ask me
anything:

- Run documents (analysis, plan, test cases) are shared in the repo, and that
  is the team's choice — save it for the whole team, not just this machine.
- Put the Development documents under `docs/changes`, not the folder acs
  proposes.
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
