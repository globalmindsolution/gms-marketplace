---
description: >-
  /acs:create-architecture re-run after a major architectural shift: the
  repo's doc set still describes an export-worker container, a Redis queue
  and a nightly-export flow that the latest commit removed, and misses the
  new orders API. It should regenerate the same doc set in place -- stale
  container, datastore and flow gone, the orders API and its flow added, the
  still-true list-customers flow kept -- push its delivery branch, and report
  the failed gh PR step as a finding.
expected_outcome: >-
  hld/c4-container.md and hld/deployment.md no longer mention export-worker
  or Redis; lld/contracts.md documents GET /orders with customer_id and no
  export queue; a new lld/flows/list-orders.md sequence diagram; the overview
  lists list-customers and list-orders but not nightly-export;
  lld/flows/list-customers.md kept; a task/EVAL-1-* branch pushed; result.json
  records the gh failure and no PR.
tags: [behaviour]
max_turns: 150
timeout_seconds: 3000
allowed_tools: [Read, Glob, Grep, Skill, Bash, Write, Edit, Agent]
---

Run the /acs:create-architecture skill to regenerate our architecture docs
in docs/architecture/ after a major shift: the last commit removed the
nightly export worker and its Redis queue and added an orders API. The docs
still describe the old system. Everything it would ask me is answered below.
Treat all of it as confirmed and do not ask me anything.

- Containers now: exactly one, the `shop` Python 3 service. The
  export-worker container and Redis are gone for good; nothing replaced them.
- Flows for lld/flows/: exactly two, in this order: `list-customers`
  (unchanged: GET /customers?offset=&limit=, 20 per page by default) and a new
  `list-orders` (a shopper client calls GET /orders?customer_id=&offset=&limit=
  and gets one customer's orders). The `nightly-export` flow no longer exists:
  remove its file.
- Deployment: the service runs as a single container behind a load
  balancer; there is no cron job any more.
- Anything else you would confirm: take what the code and the PRD say.

Pushing to origin works from this machine, but there is no GitHub access
here: when a gh call fails, handle it the way the skill says to, and finish.
