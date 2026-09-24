---
description: >-
  The explicit command must keep resolving: a delivery-path leg is invoked
  directly to resume an interrupted /acs:code run on the trivial path. The
  leg is dispatched by /acs:code, never chosen by a user from a description
  (ADR-0095 judges the path from plan.md), so this probe covers the one
  invocation that is legitimately explicit.
expected_outcome: Routes to acs:code-trivial.
tags: [routing, explicit]
max_turns: 10
allowed_tools: [Skill]
---

/acs:code-trivial
