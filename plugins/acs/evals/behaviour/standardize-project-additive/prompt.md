---
description: >-
  The standardize-project leg on an existing Python repo that has a
  pre-commit config and an architecture set but no CI workflow, no coverage
  config and no principles/standards doc sets. It must add the missing
  tooling as new files, recommend the missing doc sets as follow-ups instead
  of authoring them, and never touch existing source.
expected_outcome: >-
  Skill(acs:standardize-project) fires; a CI workflow is created; nothing new
  under src/, tests/ or docs/; src/shop/__init__.py is unchanged; result.json
  carries recommended_follow_ups naming the principles set. The PR step fails
  (no forge) and is reported.
tags: [behaviour]
max_turns: 150
timeout_seconds: 2400
allowed_tools: [Read, Glob, Grep, Skill, Bash, Write, Edit, Agent]
---

Run the /acs:standardize-project skill on this repo: audit it against its
architecture docs and acs's tooling expectations, and add only what's
missing. Answers up front: the coverage target stays at 90%, CI is GitHub
Actions, we don't want an e2e suite, keep our existing pre-commit hook as it
is, and keep the default branch and commit formats. We don't have principles
or standards docs yet -- don't write them, just tell me. Don't ask me
anything; record anything you had to assume. If pushing or opening the PR
fails, stop there and tell me what happened.
