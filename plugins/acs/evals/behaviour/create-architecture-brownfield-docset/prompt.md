---
description: >-
  /acs:create-architecture on a shipped codebase that has a PRD and no
  architecture docs, with every reverse-engineering point answered up front.
  It should write the high-level design only -- the ten default hld/ files,
  cross-cutting conventions and API landscape included, nothing under lld/ --
  grounded in the real code, push its delivery branch to origin, and report
  the failed gh PR step as a finding.
expected_outcome: >-
  The ten default hld/ files exist under docs/architecture/hld/ (overview,
  tech-stack, cross-cutting, the three C4 views, data-model,
  integration-map, deployment, project-structure) and no lld/ file was
  written; integration-map.md is a Mermaid flowchart naming the real
  /customers and /health APIs; cross-cutting.md carries its four required
  sections and the code's offset/limit pagination; hld/tech-stack.md opens
  with version front matter, status implemented, EVAL-1 in tickets
  (ADR-0122); a task/EVAL-1-* branch is
  pushed with upstream set; result.json records the gh failure and no PR.
tags: [behaviour]
max_turns: 150
timeout_seconds: 3000
allowed_tools: [Read, Glob, Grep, Skill, Bash, Write, Edit, Agent]
---

Run the /acs:create-architecture skill to document this repo's current
architecture against the PRD in docs/product/. Everything it would ask me is
answered below. Treat all of it as confirmed and do not ask me anything.

- Containers: one deployable container, the `shop` Python 3 service (package
  src/shop). There is no datastore yet: customer listing returns in-memory
  data. The payments gateway in the PRD is a planned external system, not
  built yet.
- APIs: `shop` exposes two synchronous HTTP endpoints and nothing else --
  GET /health (a load balancer's probe, returns `ok`) and
  GET /customers?offset=&limit= (a shopper client lists customers, 20 per
  page by default). There are no events, queues or consumed APIs yet.
- Deployment: the service runs as a single container behind a load balancer;
  there is no CI configuration in the repo yet.
- Anything else you would confirm: take what the code and the PRD say.

Pushing to origin works from this machine, but there is no GitHub access
here: when a gh call fails, handle it the way the skill says to, and finish.
