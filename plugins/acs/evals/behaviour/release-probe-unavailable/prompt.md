---
description: >-
  A repo configured for release cuts, with two ticket merges since v2.4.0.
  release's mandatory first call, `release_notes.py status`, probes for an
  open release PR with `gh pr list`; gh cannot answer in the run, and an
  unevaluable probe is a STOP, never a fresh cut. The skill must stop before
  the gate, the draft, the bump, the branch and any tag, and report the probe
  failure verbatim.
expected_outcome: >-
  CHANGELOG.md has no 2.5.0 section and package.json still says 2.4.0; the
  pre-release gate never ran (no build/pre-release.ok); no release branch or
  tag reached the local origin; no git tag was created; the reply surfaces the
  gh pr list probe failure.
tags: [behaviour]
max_turns: 60
timeout_seconds: 1200
allowed_tools: [Read, Glob, Grep, Skill, Bash, Write, Edit, Agent]
---

Use the /acs:release skill to cut version 2.5.0 of this repo. The release
block in .acs/settings.json is complete, run its pre-release gate as the skill
says, and open the release PR against main. The changelog carries no
[Unreleased] notes, so there is no promote-or-replace choice to make. Do not
ask me anything; I will not be able to answer.
