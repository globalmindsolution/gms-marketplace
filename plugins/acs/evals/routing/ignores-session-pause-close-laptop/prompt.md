---
description: >-
  A request to pause the user's OWN session and resume later. It routed to
  /acs:handoff while that skill was the session handoff; ADR-0131 made
  /acs:handoff the member-to-member ticket handoff and retired the session
  handoff, because every step records its state and `/acs:ship <ID>` resumes
  a run from its cursor in any session. So it is answered in prose and no
  skill should fire; /acs:handoff firing here means its description still
  reads as a session pause. It also borrows /acs:ship's vocabulary
  (continuing a run): pointing at `/acs:ship <ID>` in prose is the right
  answer, invoking it is not.
expected_outcome: Invokes no skill at all.
tags: [routing, control]
max_turns: 1
allowed_tools: [Skill]
---

I'm not continuing right now — I'm about to close my laptop. Wrap up the step in flight and give me the exact command to continue later.
