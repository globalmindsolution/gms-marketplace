---
description: >-
  /acs:create-prd on a shipped codebase with no PRD, every product fact
  supplied up front. It should write docs/product/prd.md with the eight
  required sections and the stated facts, a roadmap mapping milestones to
  release versions, and leave both documents as uncommitted local changes
  listed in states.files -- no ticket, branch, commit, push or PR (ADR-0127).
expected_outcome: >-
  docs/product/prd.md and docs/product/roadmap.md written from the stated
  facts, each opening with version front matter at status proposed,
  version 1, and left uncommitted on main (HEAD still the scaffold's commit,
  nothing pushed), the step finished with both files in states.files and no
  PR, and a reply that lists the files and points at /acs:create-pr.
tags: [behaviour]
max_turns: 150
timeout_seconds: 2400
allowed_tools: [Read, Glob, Grep, Skill, Bash, Write, Edit, Agent]
---

Run the /acs:create-prd skill to write the first PRD and roadmap for this
repo. There is no PRD yet; the code under src/shop (customer listing and a
health check) is what has shipped so far. Everything the skill would ask me is
answered below. Treat all of it as confirmed, including the reverse-engineered
baseline, and do not ask me anything.

- Vision: let small merchants sell online without running any infrastructure.
- Problem statement: merchants lose sales because setting up a storefront with
  payments takes weeks of engineering they cannot afford.
- Personas: Merchant (lists products, fulfils orders); Shopper (browses, pays,
  tracks orders).
- Goals and success metrics: G1 checkout that converts, with checkout
  conversion of at least 3.5% of shopper sessions by 2027-06-30; G2 a reliable
  service, with 99.9% monthly availability measured every calendar month from
  January 2027.
- Features (MoSCoW): Must: customer listing (already shipped, serves G2) and
  card checkout (serves G1). Should: order tracking (serves G1). Could: saved
  carts (serves G1). Won't: a marketplace for third-party sellers.
- Non-functional requirements: p95 API latency under 300 ms; unit test
  coverage of at least 90%.
- Constraints and assumptions: one Python 3.12 service; card payments go only
  through an external payments gateway and no card data is stored.
- Out of scope: native mobile apps; third-party sellers.
- Roadmap: milestone "Checkout" delivers card checkout in release v2.5.0;
  milestone "Order tracking" delivers order tracking in release v2.6.0.
