---
description: >-
  A non-ticket hotfix PR (#12, branch hotfix/health-casing) merged through
  merge-pr's exempt `--pr` mode. That mode resolves no ticket and writes no
  run; its first act reads the PR with gh to validate it, and gh cannot reach
  a forge in the run. The skill must stop on that failure without inventing a
  ticket, starting a run, merging the branch by another route, or deleting it.
expected_outcome: >-
  No run and no ticket appear under .git/acs/state-machine/example-shop/; main
  (checked out) does not carry the hotfix; hotfix/health-casing is still
  present locally and on the local origin; the reply says gh could not read
  the PR.
tags: [behaviour]
max_turns: 40
timeout_seconds: 900
allowed_tools: [Read, Glob, Grep, Skill, Bash, Write, Edit, Agent]
---

Use the /acs:merge-pr skill in its exempt non-ticket mode to merge PR #12
(the hotfix on branch hotfix/health-casing; it has no acs ticket), with the
configured strategy, and clean up afterwards. Do not ask me anything; I will
not be able to answer.
