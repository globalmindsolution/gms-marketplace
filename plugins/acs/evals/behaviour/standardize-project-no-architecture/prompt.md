---
description: >-
  The standardize-project leg on an existing Python repo with principles and
  standards sets and a pre-commit config but no architecture set, no CI and
  no coverage config. The missing architecture set must narrow the audit,
  never stop it: the leg adds the missing CI and coverage tooling and records
  /acs:create-architecture as a recommended follow-up instead of writing
  architecture docs.
expected_outcome: >-
  Skill(acs:standardize-project) fires; a CI workflow is created; nothing new
  under src/, tests/ or docs/; the leg's result.json recommends
  /acs:create-architecture; src/shop/__init__.py is unchanged. The PR step
  fails (no forge) and is reported.
tags: [behaviour]
max_turns: 150
timeout_seconds: 2400
allowed_tools: [Read, Glob, Grep, Skill, Bash, Write, Edit, Agent]
---

Run the /acs:standardize-project skill on this repo: audit it and add only
what's missing. We never wrote architecture docs -- don't write them now,
just tell me. Answers up front: the coverage target stays at 90%, CI is
GitHub Actions, we don't want an e2e suite, keep our pre-commit hook as it
is, and keep the default branch and commit formats. Don't ask me anything;
record anything you had to assume. If pushing or opening the PR fails, stop
there and tell me what happened.
