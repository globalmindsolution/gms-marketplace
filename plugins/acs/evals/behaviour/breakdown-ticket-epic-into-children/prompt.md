---
description: >-
  /acs:breakdown-ticket on an existing epic (EVAL-1, order tracking, feature
  order-tracking) whose tech design is approved and whose Rollout & migration
  table names three child slices, with the breakdown confirmed up front in the
  request. The skill should mint exactly the three confirmed children through
  new-ticket.py --parent, each tracing the epic as its parent, inheriting its
  features and carrying its confirmed acceptance criteria, leave the epic's
  own record untouched apart from its children list, and close its
  breakdown-ticket step -- in one confirmation, without asking anything or
  allocating a new id.
expected_outcome: >-
  EVAL-1's ticket.json lists children EVAL-2, EVAL-3, EVAL-4 and is still the
  epic titled Order tracking; exactly three child tickets were minted in the
  workspace (no ticket file enters the repo), each with parent EVAL-1,
  needs_design false, the features ["order-tracking"] and a non-empty
  acceptance-criteria list; the breakdown-ticket step state records completed.
tags: [behaviour]
max_turns: 100
timeout_seconds: 1800
allowed_tools: [Read, Glob, Grep, Skill, Bash, Write, Edit, Agent]
---

Run the /acs:breakdown-ticket skill with the argument `EVAL-1`: break the
epic EVAL-1 (Order tracking) down into its child tickets now that its tech
design is approved and published at
docs/architecture/lld/order-tracking/EVAL-1/tech-design.md.

I can't answer questions during this run, so here is my confirmation of the
breakdown — don't ask me anything. I confirm the three slices in the design's
Rollout & migration table, exactly as written, as the children, one ticket per
slice and no others, all priority medium, no due dates:

1. "Carrier status webhooks" — story, 3 points. Acceptance criteria:
   - POST /webhooks/carrier/{carrier} with a valid signature stores the status change against its order and returns 204
   - A callback with a missing or invalid signature is rejected with HTTP 401 and stores nothing
2. "Order status page" — story, 2 points. Acceptance criteria:
   - GET /orders/{id}/status returns the order's latest status and its full status history, newest first
   - An unknown order id returns HTTP 404
3. "Status-change emails" — task, 2 points. Acceptance criteria:
   - Every stored status change sends one email to the order's shopper naming the new status

Every child keeps the epic's feature. Leave the epic's own title, description
and acceptance criteria as they are.
Take the skill all the way through: children minted and the step finished.
