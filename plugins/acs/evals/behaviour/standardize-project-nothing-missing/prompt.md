---
description: >-
  The standardize-project leg on a repo that already has everything it
  audits for: architecture set with project-structure.md, principles and
  standards sets, CI, pre-commit, and coverage config failing below 90%; no
  e2e suite configured. The audit must find nothing to scaffold, add no file,
  recommend none of the sets that already exist, and still record its
  result.
expected_outcome: >-
  Skill(acs:standardize-project) fires; its result.json exists and
  recommends neither /acs:create-principles, /acs:create-standards nor
  /acs:create-architecture; no CI, tooling or docs file is created; the
  existing CI workflow is unchanged.
tags: [behaviour]
max_turns: 150
timeout_seconds: 2400
allowed_tools: [Read, Glob, Grep, Skill, Bash, Write, Edit, Agent]
---

Run the /acs:standardize-project skill on this repo: audit it against its
docs and acs's tooling expectations, and add only what's missing -- I think
we're already fully set up, so tell me if there's nothing to do. Answers up
front: the coverage target stays at 90%, CI is GitHub Actions, and we don't want
an e2e suite. Don't ask me
anything; record anything you had to assume. If a PR step fails or there is
nothing to put in a PR, stop there and tell me.
