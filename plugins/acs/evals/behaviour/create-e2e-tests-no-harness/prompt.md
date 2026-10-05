---
description: >-
  A ticket whose test-cases.md (uncommitted on main, like its code --
  ADR-0127) types two cases e2e, in a repo that configures no e2e suite and
  has no e2e harness at all. The skill must not invent a runner or a layout:
  it should write nothing and finish needs_input (status interrupted,
  stop_reason needs_input) with the harness question.
expected_outcome: >-
  The EVAL-1 run's create-e2e-tests result interrupted with stop_reason
  needs_input; nothing created outside .acs/; .acs/settings.json still
  configures no suite; nothing committed (HEAD still main, its reflog
  unchanged); the reply asks where/how e2e suites should run; no questions
  asked mid-run.
tags: [behaviour]
max_turns: 60
timeout_seconds: 1500
allowed_tools: [Read, Glob, Grep, Skill, Bash, Write, Edit, Agent]
---

Run the /acs:create-e2e-tests skill for ticket EVAL-1. The implementation is
done and left uncommitted in the working tree on main, and the ticket's test
cases are in its test-cases.md. Do not push. I am not available to answer
questions: do not ask me anything during the run. If the skill needs a
decision that only I can make, stop where the skill says to and leave the
question in your report.
