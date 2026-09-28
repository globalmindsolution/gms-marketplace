---
description: >-
  /acs:code on iteration 2 of the review loop. /acs:review-code already ran on
  EVAL-1 and left a verdict with one confirmed blocking finding, F-1-1:
  page_bounds computes 0-based bounds for 1-based pages. /acs:code must read
  the verdict, fix the finding test-first on the same ticket branch as a new
  commit, and answer F-1-1 by id in its result.
expected_outcome: >-
  acs:code invoked; page_bounds starts at (page - 1) * per_page; a new commit
  on task/EVAL-1-add-1-based-page-numbers-to-the-customer; an iter-2
  implementer report; the code step's result.json answers F-1-1 as fixed.
tags: [behaviour]
max_turns: 120
timeout_seconds: 2400
allowed_tools: [Read, Glob, Grep, Skill, Bash, Write, Edit, Agent]
---

Run the /acs:code skill for ticket EVAL-1. The review of its first
implementation has already run and left blocking findings in its verdict; fix
them, test-first, on the ticket branch that is checked out now, and commit the
fix there as a new commit. Use the plan's own delivery path and file map as
they are recorded. Don't push, don't re-run the review or open a PR, and don't
ask me anything: the verdict says what is wrong and what would make it right.
Finish the code step when you are done.
