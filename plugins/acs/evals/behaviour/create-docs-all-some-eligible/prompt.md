---
description: >-
  /acs:create-docs all on a repo that already ships the quality and
  principles sets and has the operations set in flight on delivery ticket
  EVAL-1. Only standards is eligible: it should run standards alone on a new
  delivery ticket, grounded in the principles set on disk, leave the other
  three sets and EVAL-1 untouched, report each ineligible set with its
  reason, push the standards branch, and report the failed gh PR step.
expected_outcome: >-
  EVAL-2 minted for the standards set and no third ticket; the three
  docs/standards/ files written, coding-standards.md carrying the principles'
  ValueError rule; nothing under docs/quality, docs/operations or
  docs/principles created and EVAL-1 not finished; a task/EVAL-2-* branch
  pushed; EVAL-2's result.json records the gh failure and no PR; the reply
  names why quality, principles and operations were skipped.
tags: [behaviour]
max_turns: 150
timeout_seconds: 3000
allowed_tools: [Read, Glob, Grep, Skill, Bash, Write, Edit, Agent]
---

Run the /acs:create-docs skill for `all` the doc sets, so that every set this
repo is still missing gets written. For any set that runs, these are the
confirmed facts; treat them as confirmed and do not ask me anything:

- Standards: snake_case modules, functions and variables, PascalCase
  classes, UPPER_SNAKE_CASE constants; ruff format and ruff check at
  100-character lines via pre-commit; pytest with one
  `tests/test_<module>.py` per module.
- Operations: semantic versions tagged `vX.Y.Z`, on-call escalates to the
  tech lead after 15 minutes, the PRD's SLOs, nightly /acs:test at 02:00 UTC.
- Anything else a set needs: take it from the PRD, the architecture set and
  the doc sets already in the repo.

Pushing to origin works from this machine, but there is no GitHub access
here: when a gh call fails, handle it the way the skill says to, and finish.
