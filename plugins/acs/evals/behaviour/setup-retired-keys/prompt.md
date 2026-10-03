---
description: >-
  /acs:setup re-run on a repo whose .acs/settings.json still carries two
  retired keys from an older acs (workspace_path, prd_path). setup must name
  both and say they are ignored -- and where state lives now -- while
  keeping the defaults, installing no CI, and leaving the rest of the file
  (the ticket prefix) intact.
expected_outcome: >-
  The reply names workspace_path and prd_path as retired/ignored; no CI file
  is created; .acs/settings.json still holds ticket_prefix EVAL.
tags: [behaviour]
max_turns: 30
timeout_seconds: 600
allowed_tools: [Read, Glob, Grep, Skill, Bash, Write, Edit, Agent]
---

We set acs up in this repo with an old version a long time ago. Run the
/acs:setup skill again and check everything is in order. Keep the
default settings and don't add any CI checks. Don't ask
me anything; tell me if anything in our config is out of date.
