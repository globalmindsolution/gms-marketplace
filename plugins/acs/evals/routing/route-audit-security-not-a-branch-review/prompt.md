---
description: >-
  Borrows the vocabulary of /acs:review-code on purpose -- a review, findings,
  a PR and a diff -- while the request still belongs to this skill: the whole
  repository as it stands, not a changeset, checked for security weaknesses and
  reported. It tests that the description, not a keyword, decides the route.
  Never names the skill.
expected_outcome: Routes to acs:audit-security.
tags: [routing, description, confusable]
max_turns: 1
allowed_tools: [Skill]
---

Not a review of my branch or this PR's diff. I want the entire repository as it is on main checked for security vulnerabilities -- every finding with its CWE and file:line -- whatever change introduced it.
