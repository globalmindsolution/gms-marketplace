---
description: >-
  /acs:create-tech-design asked for a plain story (show the app version on GET
  /health) that carries no design flag -- since ADR-0139 no ticket does. The
  gate admits it: the user's ask is the reason to design. The skill should
  run to a published, proposed tech-design.md in the ticket's design record
  folder and close its step, without refusing, flagging the ticket or
  asking anything.
expected_outcome: >-
  docs/architecture/lld/service-health/EVAL-1/tech-design.md exists; the
  create-tech-design step state records completed; the ticket still has no
  needs_design key; nothing under src/ or tests/ was created; nothing was
  committed and main is still checked out; the reply does not relay a
  refusal.
tags: [behaviour]
max_turns: 120
timeout_seconds: 1800
allowed_tools: [Read, Glob, Grep, Skill, Bash, Write, Edit, Agent]
---

Run the /acs:create-tech-design skill for ticket EVAL-1 (show the app version
on GET /health). I want the team to agree on how before anyone plans it. Take
it all the way through: the tech design reviewed, published to the ticket's
docs folder for the team to review, and the step finished.

I can't answer questions during this run, so here are my answers to the open
decisions — record them as answered, don't ask me anything:

- Read the version from the installed package metadata; fall back to
  `pyproject.toml` only when the package is not installed.
- Keep `ok` in the body exactly as it is today; the version is an added field.
- No feature flag; a plain deploy with redeploy-to-roll-back is fine.
