---
description: >-
  An indirect request in the skill's domain, phrased the way a user in the
  middle of the work would say it: the pipeline left the ticket's work
  uncommitted, and committing it in reviewable pieces is now this skill's
  job. Never names the skill.
expected_outcome: Routes to acs:create-pr.
tags: [routing, description]
max_turns: 1
allowed_tools: [Skill]
---

TKT-41 is implemented and reviewed, but nothing is committed yet. Split the changes into sensible commits on a branch, push it and open the pull request.
