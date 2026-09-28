---
description: >-
  /acs:create-docs asked for just the standards set on a repo with a PRD and
  an architecture set but no principles set, the conventions confirmed up
  front. The missing principles set must not block it or be written: it
  should mint one delivery ticket, write the three docs/standards/ files
  tailored to the confirmed conventions, push the set's delivery branch, and
  report the failed gh PR step as a finding.
expected_outcome: >-
  docs/standards/coding-standards.md, conventions.md and review-checklist.md
  with their required sections; conventions.md states snake_case naming, the
  100-character line and ruff; coding-standards.md the ValueError rule; no
  principles (or other) set written; a task/EVAL-1-* branch pushed with
  upstream set; result.json records the gh failure and no PR.
tags: [behaviour]
max_turns: 150
timeout_seconds: 2400
allowed_tools: [Read, Glob, Grep, Skill, Bash, Write, Edit, Agent]
---

Run the /acs:create-docs skill for just the `standards` set: coding
standards, conventions and a review checklist for this repo, nothing else.
We have not written engineering principles yet and I do not want them now.
Treat these as confirmed and do not ask me anything:

- Only the standards set. Do not start quality, operations or principles.
- Naming: modules, functions and variables in snake_case, classes in
  PascalCase, constants in UPPER_SNAKE_CASE (like `PAGE_SIZE`).
- Formatting: ruff format and ruff check, 100-character lines, enforced by
  pre-commit.
- Errors: reject bad input by raising `ValueError` with a message naming the
  argument; never use a bare `except:`.
- Tests: pytest, one `tests/test_<module>.py` per module, unit coverage at
  least 90% (the PRD's floor).
- Review: the author runs the tests and ruff before asking for review; the
  reviewer checks the change against coding-standards.md and conventions.md.

Pushing to origin works from this machine, but there is no GitHub access
here: when a gh call fails, handle it the way the skill says to, and finish.
