---
description: >-
  /acs:create-docs asked for just the quality set, on a repo whose PRD sets a
  90% coverage NFR and whose architecture set names pytest. It should mint one
  delivery ticket, write only docs/quality/ tailored to that stack and target,
  push the set's delivery branch to origin, and report the failed gh PR step
  as a finding.
expected_outcome: >-
  docs/quality/test-strategy.md with its five required sections and
  docs/quality/coverage-policy.md stating the 90% target measured with pytest,
  no other doc set written, a task/EVAL-1-* branch pushed with upstream set,
  and result.json recording the gh failure and no PR.
tags: [behaviour]
max_turns: 120
timeout_seconds: 2400
allowed_tools: [Read, Glob, Grep, Skill, Bash, Write, Edit, Agent]
---

Run the /acs:create-docs skill for just the `quality` set: I want the test
strategy and coverage policy for this repo, nothing else. Treat these as
confirmed and do not ask me anything:

- Only the quality set. Do not start operations, principles or standards.
- The coverage target is the PRD's: at least 90% unit test coverage, and
  missing it hard-fails the pipeline.
- Unit tests run with pytest and coverage is measured with pytest-cov, as the
  architecture set's tech stack says. There is no end-to-end suite yet.
- There is no CI configuration in the repo yet; describe the gates it should
  run.

Pushing to origin works from this machine, but there is no GitHub access
here: when a gh call fails, handle it the way the skill says to, and finish.
