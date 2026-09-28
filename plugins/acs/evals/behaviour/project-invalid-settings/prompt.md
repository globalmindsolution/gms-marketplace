---
description: >-
  /acs:project on an existing repo whose .acs/settings.json holds an invalid
  hand-set value (merge_strategy "fast-forward"). Start's settings
  validation exits 2: the skill must surface the error verbatim and stop --
  no mode reported as a verdict, no leg dispatched, no delivery ticket, and
  the user's settings file left for the user to fix.
expected_outcome: >-
  Skill(acs:project) fires; the reply quotes the merge_strategy error; no
  EVAL-1 partition or step is created; .acs/settings.json still says
  "fast-forward".
tags: [behaviour]
max_turns: 40
timeout_seconds: 900
allowed_tools: [Read, Glob, Grep, Skill, Bash, Write, Edit, Agent]
---

Run the /acs:project skill on this repo to bring its structure and tooling up
to what acs expects. Answers to anything it might ask: the coverage target
stays at 90%, CI is GitHub Actions, no e2e suite, default branch and commit
formats. Don't ask me anything. Don't change our acs settings either -- if
something about them is wrong, stop and tell me exactly what the error says.
