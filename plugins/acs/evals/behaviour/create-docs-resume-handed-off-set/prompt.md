---
description: >-
  Resume a handed-off /acs:create-docs quality run by its delivery-ticket id.
  EVAL-1's author was interrupted with test-strategy.md half written and
  coverage-policy.md not started. The run should rejoin EVAL-1 without
  minting a new ticket, finish both files, review them, push EVAL-1's
  existing branch, and report the failed gh PR step as a finding.
expected_outcome: >-
  No EVAL-2 ticket; docs/quality/test-strategy.md completed with all five
  required sections; docs/quality/coverage-policy.md written with the 90%
  target; task/EVAL-1-product-quality-doc-set pushed with upstream set; the
  result.json under runs/EVAL-1 records the gh failure and no PR.
tags: [behaviour]
max_turns: 120
timeout_seconds: 2400
allowed_tools: [Read, Glob, Grep, Skill, Bash, Write, Edit, Agent]
---

Yesterday's quality docs run was handed off before it finished. Run the
/acs:create-docs skill with the argument `EVAL-1` to resume that delivery
ticket and finish the set. The facts are the same as yesterday; treat them as
confirmed and do not ask me anything:

- The coverage target is the PRD's: at least 90% unit test coverage, and
  missing it hard-fails the pipeline.
- Unit tests run with pytest and coverage is measured with pytest-cov, as
  the architecture set's tech stack says. There is no end-to-end suite yet.
- There is no CI configuration in the repo yet; describe the gates it should
  run.

Pushing to origin works from this machine, but there is no GitHub access
here: when a gh call fails, handle it the way the skill says to, and finish.
