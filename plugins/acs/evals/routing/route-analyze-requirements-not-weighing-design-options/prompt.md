---
description: >-
  Borrows the vocabulary of /acs:create-tech-design on purpose -- it talks about
  design options -- while the request still
  belongs to this skill. It tests that the description, not a keyword,
  decides the route. Never names the skill.
expected_outcome: Routes to acs:analyze-requirements.
tags: [routing, description, confusable]
max_turns: 1
allowed_tools: [Skill]
---

Don't weigh design options for TKT-81 yet. First just tell me what the ticket actually changes, which surfaces it touches, and which of its acceptance criteria are still too vague to test.
