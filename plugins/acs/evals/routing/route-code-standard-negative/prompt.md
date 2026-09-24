---
description: >-
  A request to implement an approved plan must reach /acs:code, the entry
  point, even when the user's own wording names the standard path: which leg
  runs is read from the ticket's recorded `delivery_path`, judged once from
  the plan (ADR-0095), never inferred from how the request is phrased. This
  probe deliberately plants the word a mis-grab would key on, so the leg's
  DESCRIPTION — dispatched by /acs:code, never chosen by hand — is what has
  to hold.
expected_outcome: Does not invoke acs:code-standard.
tags: [routing, negative]
max_turns: 1
allowed_tools: [Skill]
---

TKT-1's plan is approved. It is a standard-sized change across a few modules. Implement it.
