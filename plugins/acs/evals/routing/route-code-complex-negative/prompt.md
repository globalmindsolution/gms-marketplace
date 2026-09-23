---
description: >-
  A request to implement an approved plan must reach /acs:code, the entry
  point, even when the user's own wording names the complex path: which leg
  runs is read from the ticket's recorded `delivery_path`, judged once from
  the plan (ADR-0095), never inferred from how the request is phrased. This
  probe deliberately plants the word a mis-grab would key on, so the leg's
  DESCRIPTION — dispatched by /acs:code, never chosen by hand — is what has
  to hold.
expected_outcome: Does not invoke acs:code-complex.
tags: [routing, negative]
max_turns: 10
allowed_tools: [Skill]
---

TKT-1's plan is approved and it is a complex change: several modules, a migration, and a public API. Implement it.
