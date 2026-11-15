---
description: >-
  EVAL-1 is implemented and recorded by /acs:code, and -- as every acs step now
  leaves it (ADR-0127) -- its changes sit uncommitted in the working tree on
  main, beside a note the user had lying around before the run and a WIP file
  no step recorded. create-pr is the one skill that commits: it must plan the
  commits with `acs.py pr plan-commits`, take the user's up-front approval of
  that plan, commit it with `acs.py pr commit` on a new branch (the tests and
  the code as separate commits), and leave the unrelated files out and
  uncommitted. gh cannot reach a forge, so base detection then stops it before
  the push.
expected_outcome: >-
  steps/create-pr/iter-1/commit-plan.json is written and names neither the
  user's note nor the WIP file in any group; the plan is committed through
  `acs.py pr commit` as at least two EVAL-1 commits on a new branch, none on
  main; no raw git add, commit, stash, reset or restore was run; the WIP file
  is still in the working tree; steps/create-pr/state.json records a failed
  invocation with the commits and no pr object; nothing reached the local
  origin.
tags: [behaviour]
max_turns: 60
timeout_seconds: 1200
allowed_tools: [Read, Glob, Grep, Skill, Bash, Write, Edit, Agent]
---

Run the /acs:create-pr skill for ticket EVAL-1 — the implementation is done and
sits uncommitted in the working tree. Commit it the way the skill proposes to
split it: I approve its proposed commit plan as is, no edits. Then open the
pull request against the default branch the way the skill does and tell me
where it stands, including the commits you made. Do not ask me anything; I will
not be able to answer.
