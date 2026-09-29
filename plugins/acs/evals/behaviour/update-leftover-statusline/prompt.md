---
description: >-
  /acs:update, offline, in a repo whose .claude/settings.json still carries
  a statusLine pointing at acs's retired statusline.py. The version check
  cannot complete (no network, no gh): the skill must report `failed` with
  the manual commands, and it must not edit the settings file -- the
  leftover is the user's to remove.
expected_outcome: >-
  The reply carries the `/acs:update · failed` block and the manual
  `claude plugin marketplace update gms-marketplace` command;
  .claude/settings.json still holds the statusline.py command and the
  permissions block; nothing is created under .acs/ or .claude/.
tags: [behaviour]
max_turns: 40
timeout_seconds: 900
allowed_tools: [Read, Glob, Grep, Skill, Bash, Write, Edit, Agent]
---

Run the /acs:update skill: check whether a newer acs plugin is out and run
its migration checks. I also suspect an old acs status line is still
configured somewhere in this repo -- if so, tell me what to change, I'll do
it myself. If you can't reach GitHub, don't guess the latest version: tell me
what you could and couldn't check and give me the commands to run. Don't
edit any files and don't ask me anything.
