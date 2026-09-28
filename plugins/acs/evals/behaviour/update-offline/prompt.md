---
description: >-
  /acs:update with no network and no gh credentials. The installed version is
  readable, the latest release is not: the skill must say the version check
  is unavailable, print the manual commands, finish `failed`, and write
  nothing -- never claim "up to date" or an update it could not check.
expected_outcome: >-
  The final message carries the `/acs:update · failed` completion block and
  the manual `claude plugin marketplace update gms-marketplace` command; no
  file is created under .acs/.
tags: [behaviour]
max_turns: 40
timeout_seconds: 900
allowed_tools: [Read, Glob, Grep, Skill, Bash, Write, Edit, Agent]
---

Run the /acs:update skill: check whether there's a newer acs plugin version
than the one installed, and if there is, refresh the marketplace. If you
can't reach GitHub to find out, don't guess -- tell me what you could and
couldn't check and give me the commands to run myself. Don't ask me anything.
