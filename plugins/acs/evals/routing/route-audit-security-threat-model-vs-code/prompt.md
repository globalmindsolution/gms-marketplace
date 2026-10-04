---
description: >-
  Borrows the vocabulary of /acs:create-architecture on purpose -- the HLD,
  its data-flow diagram and trust boundaries -- while the request still
  belongs to this skill: it rules out writing or redrawing the threat model
  and asks whether the code enforces the controls it requires. It tests that
  the description, not a keyword, decides the route. Never names the skill.
expected_outcome: Routes to acs:audit-security.
tags: [routing, description, confusable]
max_turns: 1
allowed_tools: [Skill]
---

Don't regenerate the HLD or redraw the data-flow diagram. Take the trust boundaries our threat model in hld/data-flow.md already draws and check that the code enforces the authentication and input validation each crossing needs -- report every gap as a security finding.
