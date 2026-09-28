---
description: >-
  /acs:create-requirements on a shipped codebase with no requirements set,
  the DRAFT baseline and its open points confirmed up front. It should
  reverse-engineer DRAFT, code-cited functional and non-functional files under
  docs/requirements/, push its delivery branch to origin, and report the
  failed gh PR step as a finding.
expected_outcome: >-
  docs/requirements/functional/customer-listing.md opens with the DRAFT marker
  and states MUST clauses grounded in the listing code, its .evidence.md
  sidecar cites src/shop/__init__.py, non-functional/performance.md carries
  the 300 ms bound, a task/EVAL-1-* branch is pushed with upstream set, and
  result.json records the gh failure and no PR.
tags: [behaviour]
max_turns: 150
timeout_seconds: 3000
allowed_tools: [Read, Glob, Grep, Skill, Bash, Write, Edit, Agent]
---

Run the /acs:create-requirements skill to bootstrap living requirements for
this repo from its existing code (there is no requirements set yet). I have
already reviewed what it will propose, so here are the answers. Treat them as
confirmed and do not ask me anything.

- DRAFT baseline confirmed, exactly these area files:
  `docs/requirements/functional/customer-listing.md` (GET /customers with
  offset and limit, 20 per page by default),
  `docs/requirements/functional/health-check.md` (GET /health returns `ok`),
  and `docs/requirements/non-functional/performance.md` (p95 API latency under
  300 ms, from the PRD's NFR1).
- The listing enforces no maximum `limit` today: record that as an open point,
  do not invent a maximum.
- The health check needs no authentication.
- Checkout and order tracking are not built yet: leave them out.

Pushing to origin works from this machine, but there is no GitHub access
here: when a gh call fails, handle it the way the skill says to, and finish.
