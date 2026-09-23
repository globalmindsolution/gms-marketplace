---
description: >-
  A natural-language request in the skill's domain, never naming the skill.
  This was a NEGATIVE probe until 2026-09-13, asserting that disable-model-
  invocation kept the model from reaching acs:install-hooks. No skill sets
  that flag now, so the same prompt states the opposite and better claim: a
  request about local git hooks should reach this skill. The prompt is
  unchanged.
expected_outcome: Routes to acs:install-hooks.
tags: [routing, description]
max_turns: 10
allowed_tools: [Skill]
---

Set up the git hooks for this repository so checks run before every commit.
