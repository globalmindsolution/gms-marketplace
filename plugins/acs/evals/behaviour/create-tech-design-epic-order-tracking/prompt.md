---
description: >-
  /acs:create-tech-design on an EPIC (order tracking, PRD F3) with the open
  decisions answered up front. The tech design is made at epic level, the
  hand-off the team reviews before any child is planned: tech-design.md
  published `proposed` with the six sections filled and at least two weighed
  options (carrier webhooks versus polling), its Risks' Rollout & migration
  laying out the child slices the epic will be broken down into -- without minting
  any child -- the step closed, and the reply naming the epic's next step,
  approval and then /acs:breakdown-ticket EVAL-1, not /acs:code.
expected_outcome: >-
  docs/architecture/lld/order-tracking/EVAL-1/tech-design.md exists with the six
  headings in order, two or more #### options under ### Options considered,
  and a ### Rollout & migration naming the child slices; no EVAL-2 exists; the
  step's state.json records completed; the final reply names
  /acs:breakdown-ticket EVAL-1.
tags: [behaviour]
max_turns: 120
timeout_seconds: 1800
allowed_tools: [Read, Glob, Grep, Skill, Bash, Write, Edit, Agent]
---

Run the /acs:create-tech-design skill for epic EVAL-1 (order tracking). Take it
all the way through: the tech design reviewed, published to the ticket's docs
folder for the team to review, and the step finished.

I can't answer questions during this run, so here are my answers to the open
decisions — record them as answered, don't ask me anything:

- We integrate two carriers. Both can push status changes to us as signed
  webhooks and both offer a status API we could poll; weigh the two and pick
  the simplest option that meets the PRD's p95 < 300 ms.
- Carrier callbacks must be authenticated; a shared secret per carrier is
  acceptable.
- Emails go through an outbound transactional email API; which provider is
  not decided and does not change the design.
- This epic will be fanned out into child tickets after the design, each one
  reviewable pull request: lay out those child slices in the rollout.
  Do not create the child tickets now.
