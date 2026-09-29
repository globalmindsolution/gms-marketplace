---
description: >-
  A repo configured for release cuts, asked to cut "2.5" -- not a
  MAJOR.MINOR.PATCH version. /acs:release fails fast on a version argument
  that is not semver-shaped, naming the expected form, and never guesses one
  (2.5.0) from the request or any file. Nothing is gated, drafted, bumped,
  branched, pushed or tagged.
expected_outcome: >-
  No command passes 2.5.0 as the version; CHANGELOG.md has no 2.5 section and
  package.json still says 2.4.0; the gate never ran (no build/pre-release.ok);
  nothing new reaches the local origin; no tag is created; the reply names the
  expected MAJOR.MINOR.PATCH form.
tags: [behaviour]
max_turns: 30
timeout_seconds: 900
allowed_tools: [Read, Glob, Grep, Skill, Bash, Write, Edit, Agent]
---

Use the /acs:release skill to cut version 2.5 of this repo and open the
release PR against main. Do not ask me anything; I will not be able to
answer.
