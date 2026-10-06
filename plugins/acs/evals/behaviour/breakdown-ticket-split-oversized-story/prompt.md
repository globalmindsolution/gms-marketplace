---
description: >-
  /acs:breakdown-ticket on an oversized STORY (EVAL-1, storefront order
  management, feature order-management) whose published plan records three
  split seams, with the split confirmed up front in the request. The skill
  should convert EVAL-1 into an epic that keeps its id and description, then
  mint exactly the three confirmed children under it through new-ticket.py
  --parent, each inheriting the order-management feature and carrying its
  confirmed acceptance criteria, and close its breakdown-ticket step -- without
  asking anything or allocating a new id for the parent.
expected_outcome: >-
  EVAL-1's ticket.json is now type epic, keeps its description and lists
  children EVAL-2, EVAL-3, EVAL-4; exactly three child tickets were minted,
  each with parent EVAL-1 and features ["order-management"], the last with its
  export criteria; result.json records converted_from story; the
  breakdown-ticket step state records completed.
tags: [behaviour]
max_turns: 100
timeout_seconds: 1800
allowed_tools: [Read, Glob, Grep, Skill, Bash, Write, Edit, Agent]
---

Run the /acs:breakdown-ticket skill with the arguments
`EVAL-1 docs/development/order-management/EVAL-1/plan.md`: the story EVAL-1
(Storefront order management) is too large for one pull request, and its plan
records where to split it.

I can't answer questions during this run, so here is my confirmation of the
split — don't ask me anything. Convert EVAL-1 into an epic that keeps its id,
and mint exactly these three children under it, one per seam in the plan, in
this order, all priority medium, every one keeping the story's feature, no due
dates:

1. "Checkout and order storage" — story, 3 points. Acceptance criteria:
   - POST /checkout charges the card through the payments gateway and creates the order
   - A declined card returns HTTP 402 with error code card_declined and creates no order
   - Orders and refunds are stored in two new tables created by a migration
2. "Refunds" — story, 2 points. Acceptance criteria:
   - POST /orders/{id}/refund refunds the charge through the payments gateway and marks the order refunded
   - A refund older than 30 days is rejected with HTTP 409 and error code refund_window_closed
3. "Merchant CSV export" — task, 2 points. Acceptance criteria:
   - GET /merchant/orders/export returns every order as CSV for accounting
   - The export lists one row per order with its id, date, total and status

There is no tech design for this work and none is needed; do not stop for one.
Take the skill all the way through: EVAL-1 converted, the children minted and
the step finished.
