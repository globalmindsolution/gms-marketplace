---
description: >-
  A repo whose release block names package.json as the version location,
  though the product has no package.json (its version is in pyproject.toml).
  release's mandatory first call, `release_notes.py status`, reads the version
  locations before any gh probe and exits 2 on the missing file. The skill
  must stop there, surface the error verbatim, and write nothing -- no gate
  run, no draft, bump, branch, push or tag, no hand-made manifest or edited
  block.
expected_outcome: >-
  No package.json is created; .acs/settings.json still names package.json;
  pyproject.toml still says 2.4.0; CHANGELOG.md has no 2.5.0 section; the
  gate never ran (no build/pre-release.ok); nothing new reaches the local
  origin; no tag is created; the reply names package.json.
tags: [behaviour]
max_turns: 40
timeout_seconds: 900
allowed_tools: [Read, Glob, Grep, Skill, Bash, Write, Edit, Agent]
---

Use the /acs:release skill to cut version 2.5.0 of this repo. The release
block in .acs/settings.json is the configuration to use; run its pre-release
gate as the skill says, and open the release PR against main. The changelog
carries no [Unreleased] notes. Do not ask me anything; I will not be able to
answer.
