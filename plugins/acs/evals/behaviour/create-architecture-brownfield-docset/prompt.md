---
description: >-
  /acs:create-architecture on a shipped codebase that has a PRD and no
  architecture docs, with the flow list and every reverse-engineering point
  answered up front. It should write the full HLD/LLD doc set under
  docs/architecture/, grounded in the real code, push its delivery branch to
  origin, and report the failed gh PR step as a finding.
expected_outcome: >-
  The eight hld/ files, lld/contracts.md and the two confirmed flow files
  exist under docs/architecture/, the list-customers flow is a Mermaid
  sequence diagram, the contracts name the real /customers offset/limit API,
  a task/EVAL-1-* branch is pushed with upstream set, and result.json records
  the gh failure and no PR.
tags: [behaviour]
max_turns: 150
timeout_seconds: 3000
allowed_tools: [Read, Glob, Grep, Skill, Bash, Write, Edit, Agent]
---

Run the /acs:create-architecture skill to document this repo's current
architecture against the PRD in docs/product/. Everything it would ask me is
answered below. Treat all of it as confirmed and do not ask me anything.

- Flows for lld/flows/: exactly two, in this order: `list-customers` (a
  shopper client calls GET /customers?offset=&limit= and gets a page of
  customers, 20 per page by default) and `health-check` (a load balancer calls
  GET /health and gets `ok`).
- Containers: one deployable container, the `shop` Python 3 service (package
  src/shop). There is no datastore yet: customer listing returns in-memory
  data. The payments gateway in the PRD is a planned external system, not
  built yet.
- Deployment: the service runs as a single container behind a load balancer;
  there is no CI configuration in the repo yet.
- Anything else you would confirm: take what the code and the PRD say.

Pushing to origin works from this machine, but there is no GitHub access
here: when a gh call fails, handle it the way the skill says to, and finish.
