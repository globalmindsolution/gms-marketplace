---
description: >-
  An indirect request in the skill's domain, phrased the way a user in the
  middle of the work would say it, with the context it needs stated in the
  prompt. Never names the skill.
expected_outcome: Routes to acs:install-hooks.
tags: [routing, description]
max_turns: 1
allowed_tools: [Skill]
---

My .git/hooks folder got wiped after I re-initialised the repo, and now commits go through with any message at all. Repair the local checks.
