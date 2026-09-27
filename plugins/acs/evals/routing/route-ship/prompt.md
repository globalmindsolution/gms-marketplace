---
description: >-
  A natural-language request in the skill's domain, never naming the skill.
  The prompt names a TICKET, because a ticket is what the skill takes: since
  the skills-independence refactor /acs:ship parses its argument as "a
  ticket id, and nothing else" and refuses a bare prompt, redirecting to
  /acs:create-ticket. The 1.3.0 prompt asked for a password-reset flow to be
  shipped from nothing and routed to acs:create-ticket on 5/5 runs of the
  2026-09-13 measurement — the documented correct answer to a prompt
  carrying no ticket. That probe was measuring a contract the plugin no
  longer has.
expected_outcome: Routes to acs:ship.
tags: [routing, description]
max_turns: 1
allowed_tools: [Skill]
---

TKT-1 is ready to go. Take it from here to a pull request for me — I don't want to drive each step myself.
