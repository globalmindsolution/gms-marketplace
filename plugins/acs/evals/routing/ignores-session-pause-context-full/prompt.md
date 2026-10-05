---
description: >-
  A request to pause the user's OWN session and resume later. It routed to
  /acs:handoff while that skill was the session handoff; ADR-0131 made
  /acs:handoff the member-to-member ticket handoff and retired the session
  handoff, because every step records its state and `/acs:ship <ID>` resumes
  a run from its cursor in any session. So it is answered in prose and no
  skill should fire; /acs:handoff firing here means its description still
  reads as a session pause.
expected_outcome: Invokes no skill at all.
tags: [routing, control]
max_turns: 1
allowed_tools: [Skill]
---

We're halfway through the implementation step on TKT-8 and my context window is nearly full. Flush what you know so a fresh session can resume it without losing anything.
