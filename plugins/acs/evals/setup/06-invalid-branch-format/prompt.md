---
description: >-
  A branch format with no ticket id, which acs cannot use: every skill finds
  the current ticket from the branch name. Setup must explain and leave no
  broken configuration behind.
expected_outcome: >-
  No settings file; the reply explains why the branch format needs {ticket_id}
  and offers a working alternative.
tags: [setup]
max_turns: 30
timeout_seconds: 600
allowed_tools: [Read, Glob, Grep, Skill, Bash, Write, Edit]
---

Set up acs with the branch name format `{type}/{slug}` -- I don't want ticket
ids in our branch names. Keep everything else default and skip CI.
