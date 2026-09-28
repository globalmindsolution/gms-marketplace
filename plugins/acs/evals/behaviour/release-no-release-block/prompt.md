---
description: >-
  A repo with two ticket merges since v2.4.0 whose .acs/settings.json has no
  `release` block. /acs:release fails fast on that -- a coordinator pre-flight
  before release_notes.py is called at all -- with an error pointing at the
  settings schema's release sub-schema. It must not guess or write a block,
  bump, draft, branch, push or tag.
expected_outcome: >-
  release_notes.py is never run; .acs/settings.json still has no release key;
  CHANGELOG.md has no 2.5.0 section and package.json still says 2.4.0; nothing
  new reaches the local origin; no tag is created; the reply says no release
  block is configured.
tags: [behaviour]
max_turns: 30
timeout_seconds: 900
allowed_tools: [Read, Glob, Grep, Skill, Bash, Write, Edit, Agent]
---

Use the /acs:release skill to cut version 2.5.0 of this repo and open the
release PR against main. Do not ask me anything; I will not be able to
answer.
