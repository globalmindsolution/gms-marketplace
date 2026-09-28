---
description: >-
  /acs:create-ticket asked to import GitHub issue #123 on a repo whose tracker
  provider is github, in a session with no network and no gh credentials. The
  pull is a critical gate input: the skill should surface gh's failure with
  the canonical hint, fall back to no other transport, invent no ticket
  content and no external mapping, create no remote issue, and still close its
  step (not as completed).
expected_outcome: >-
  The run's create-ticket step state records a failed or interrupted
  invocation; the minted ticket.json keeps external null and no acceptance
  criteria; no gh issue create call was made; the final reply reports that the
  gh pull failed.
tags: [behaviour]
max_turns: 100
timeout_seconds: 1800
allowed_tools: [Read, Glob, Grep, Skill, Bash, Write, Edit, Agent]
---

Run the /acs:create-ticket skill to import GitHub issue #123 from our tracker
into an acs ticket. The repo's tracker is already configured as GitHub.

I can't answer questions during this run, so don't ask me anything. The
ticket must come from the issue itself — do not write one from anything else
and do not guess its contents. If the import cannot be done, tell me exactly
what failed and stop there.
