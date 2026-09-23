---
description: >-
  A natural-language request in the skill's domain, never naming the skill.
  This was a NEGATIVE probe until 2026-09-13, asserting that disable-model-
  invocation kept the model from reaching acs:update. No skill sets that
  flag now, so the same prompt states the opposite and better claim: a
  request about a newer plugin version should reach this skill. The prompt
  is unchanged.
expected_outcome: Routes to acs:update.
tags: [routing, description]
max_turns: 10
allowed_tools: [Skill]
---

Check whether there is a newer version of the acs plugin available.
