---
description: >-
  /acs:setup adding the convention check on a repo whose .gitignore ignores
  all of .acs/. The install lands, but the checker CI must read is
  gitignored: setup must relay that warning and leave the user's .gitignore
  exactly as it is -- the fix is the user's to choose.
expected_outcome: >-
  .github/workflows/acs-conventions.yml and .acs/ci/check-conventions.py are
  created; .gitignore still reads `.acs/` and `*.pyc` and nothing else; the
  reply warns that .acs/ is gitignored and names the fix.
tags: [behaviour]
max_turns: 40
timeout_seconds: 900
allowed_tools: [Read, Glob, Grep, Skill, Bash, Write, Edit, Agent]
---

Run the /acs:setup skill for this repo: keep the default ticket prefix and
add the convention check to CI. I'm not an admin, so
leave branch protection alone. Don't ask me anything, and don't commit
anything -- just tell me what I need to stage and anything I need to sort
out myself.
