---
description: >-
  /acs:create-architecture re-run after a major architectural shift: the
  repo's HLD still describes an export-worker container and a Redis queue
  that the latest commit removed, misses the new orders API, and predates
  hld/cross-cutting.md and hld/integration-map.md; an lld/ folder of
  per-ticket contracts and flows sits beside it. It should regenerate the HLD
  in place -- stale container and datastore gone, the orders API added, the
  two missing HLD files created -- leave every lld/ file exactly as it was,
  push its delivery branch, and report the failed gh PR step as a finding.
expected_outcome: >-
  hld/c4-container.md and hld/deployment.md no longer mention export-worker
  or Redis; hld/c4-component.md and the new hld/integration-map.md name the
  orders API; hld/cross-cutting.md is created; hld/c4-container.md carries
  version front matter with EVAL-1 in tickets; the run's iter-1/gaps.md files
  the export worker / Redis as unimplemented and the orders API as
  undocumented; lld/contracts.md,
  lld/flows/list-customers.md and lld/flows/nightly-export.md are byte for
  byte as the scaffold left them and no lld/ file is added; a task/EVAL-1-*
  branch is pushed; result.json records the gh failure and no PR.
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
- APIs now: `shop` exposes three synchronous HTTP endpoints -- GET /health,
  GET /customers?offset=&limit= (unchanged, 20 per page by default) and the
  new GET /orders?customer_id=&offset=&limit= (one customer's orders). There
  is no queue and no async consumer any more.
- Deployment: the service runs as a single container behind a load
  balancer; there is no cron job any more.
- Anything else you would confirm: take what the code and the PRD say.

Pushing to origin works from this machine, but there is no GitHub access
here: when a gh call fails, handle it the way the skill says to, and finish.
