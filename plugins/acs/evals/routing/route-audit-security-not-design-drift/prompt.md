---
description: >-
  Borrows the vocabulary of /acs:audit-design on purpose -- an audit, the
  architecture docs, the code, a report of gaps -- while the request still
  belongs to this skill: it rules out comparing the design with the code and
  asks whether the code is exploitable. It tests that the description, not a
  keyword, decides the route. Never names the skill.
expected_outcome: Routes to acs:audit-security.
tags: [routing, description, confusable]
max_turns: 1
allowed_tools: [Skill]
---

I don't need to know whether the architecture docs still match the code -- they do. I need to know whether the code is safe: exploitable weaknesses, hard-coded credentials, insecure configuration. Report them by severity.
