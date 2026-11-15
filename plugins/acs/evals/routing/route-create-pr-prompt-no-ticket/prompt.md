---
description: >-
  A run with no ticket: the work came from a prompt, not a ticket id, and no
  acs skill needs a ticket -- this one takes a ticket id, a prompt or the
  current run. The change is already made and only needs committing and
  shipping, with the context it needs stated in the prompt. Never names the
  skill.
expected_outcome: Routes to acs:create-pr.
tags: [routing, description]
max_turns: 1
allowed_tools: [Skill]
---

There's no ticket for the login-timeout fix I asked for earlier; the change is sitting uncommitted in the working tree. Commit it in sensible pieces and open a pull request so the team can review it.
