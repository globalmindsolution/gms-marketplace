---
description: >-
  An indirect request in the skill's domain, phrased the way a user in the
  middle of the work would say it, with the context it needs stated in the
  prompt. Never names the skill.
expected_outcome: Routes to acs:release.
tags: [routing, description]
max_turns: 1
allowed_tools: [Skill]
---

Product signed off on 4.2.0 this morning. Do the version cut: CHANGELOG section dated today, package.json and the other configured version refs bumped. Tagging and publishing happen later in CI, so don't tag anything.
