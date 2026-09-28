---
description: >-
  /acs:install-hooks in a clone with no .acs/ci/ and a hand-written, non-acs
  pre-push hook. It must copy the checker and hook scripts from the plugin
  templates, install the commit-msg hook, and leave the user's pre-push hook
  exactly as it was.
expected_outcome: >-
  .acs/ci/check-conventions.py is created; .git/hooks/commit-msg runs the
  checker; .git/hooks/pre-push still holds the user's test hook and no acs
  checker; the reply says pre-push was left alone and that .acs/ci/ needs
  committing.
tags: [behaviour]
max_turns: 40
timeout_seconds: 900
allowed_tools: [Read, Glob, Grep, Skill, Bash, Write, Edit, Agent]
---

Run the /acs:install-hooks skill so this clone checks our branch names and
commit messages locally before anything reaches CI. Use plain git hooks --
we don't use the pre-commit framework here. I already have my own pre-push
hook that runs the tests: leave it exactly as it is, don't overwrite it and
don't merge anything into it. Don't commit anything either; just tell me
what I need to commit. Don't ask me anything.
