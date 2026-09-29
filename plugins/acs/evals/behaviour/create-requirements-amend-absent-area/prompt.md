---
description: >-
  /acs:create-requirements amend mode: a populated requirements set that
  misses the newly shipped orders API. It should mint an "Amend
  requirements:" delivery ticket, add ONLY the absent order-listing area file
  (DRAFT, code-cited in its evidence sidecar), leave every existing area file
  byte-for-byte, push its delivery branch, and report the failed gh PR step
  as a finding.
expected_outcome: >-
  EVAL-1 titled "Amend requirements: ..."; a new
  docs/requirements/functional/order-listing.md opening with the DRAFT
  marker and stating MUST clauses for GET /orders and customer_id, its
  .evidence.md sidecar citing src/shop/orders.py; customer-listing.md and
  performance.md unchanged; no other area file created; a task/EVAL-1-*
  branch pushed; result.json records the gh failure and no PR.
tags: [behaviour]
max_turns: 150
timeout_seconds: 3000
allowed_tools: [Read, Glob, Grep, Skill, Bash, Write, Edit, Agent]
---

Run the /acs:create-requirements skill with the argument `add the missing
order-listing area` to amend our requirements set in docs/requirements/. It
already covers customer listing, the health check and performance, all
confirmed by the product owner; the orders API we shipped since
(src/shop/orders.py) has no requirements yet. I have reviewed what the skill
will propose, so here are the answers. Treat them as confirmed and do not ask
me anything.

- Augment exactly one area: add `docs/requirements/functional/order-listing.md`
  for GET /orders?customer_id=&offset=&limit= (customer_id is required, 20 per
  page by default).
- Every existing area file stays exactly as it is, word for word.
- The orders listing enforces no maximum `limit` today: record that as an
  open point, do not invent one.

Pushing to origin works from this machine, but there is no GitHub access
here: when a gh call fails, handle it the way the skill says to, and finish.
