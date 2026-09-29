---
description: >-
  /acs:install-hooks in a clone whose team set custom formats with /acs:setup
  (commit subject `{ticket_id}: {summary}`, commit-message check turned on).
  The installed hooks must enforce those formats, not acs's defaults: the
  run installs both hooks with the committed installer, leaves the settings
  alone, and shows the commit-msg hook accepting `EVAL-7: Add wishlist
  export` and refusing `EVAL-7 Add wishlist export`.
expected_outcome: >-
  .git/hooks/commit-msg and .git/hooks/pre-push run the committed checker;
  .acs/settings.json still carries the custom formats and the enabled
  commit-message check; the reply reports the colon subject passing and the
  default-format subject rejected.
tags: [behaviour]
max_turns: 40
timeout_seconds: 900
allowed_tools: [Read, Glob, Grep, Skill, Bash, Write, Edit, Agent]
---

Run the /acs:install-hooks skill in this clone. Our team changed the commit
and branch formats with /acs:setup, and I want the local hooks to enforce
exactly what we configured, not acs's defaults. Plain git hooks, no
pre-commit framework. Once they're in, prove it: run the installed commit-msg
hook against the subject `EVAL-7: Add wishlist export` and against
`EVAL-7 Add wishlist export`, and tell me which one it accepts. Don't change
our settings, don't commit anything, and don't ask me anything.
