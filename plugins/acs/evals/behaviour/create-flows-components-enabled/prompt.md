---
description: >-
  /acs:create-flows on the order-cancellation story (EVAL-1, feature
  orders) in a repo whose design.lld_types adds the opt-in component-detail
  and class types; the request does not mention the setting. Beside the
  cancel-order flow and the order's state machine, it should write
  components/orders.md with an internals flowchart and a classDiagram,
  versioned like the rest, record it in states.files and both types in
  states.types, and write no code.
expected_outcome: >-
  docs/architecture/lld/orders/flows/cancel-order.md and state-order.md
  exist, the state machine holding placed --> cancelled and paid -->
  cancelled; docs/architecture/lld/orders/components/orders.md has version
  front matter and Responsibility, Internals (flowchart), Types
  (classDiagram) and Collaborators in order; no code and no document
  outside the feature's flows/ and components/ (bar the feature README) is
  created; state.json is completed with the component in states.files and
  component-detail and class in states.types.
tags: [behaviour]
max_turns: 150
timeout_seconds: 2400
allowed_tools: [Read, Glob, Grep, Skill, Bash, Write, Edit, Agent]
---

Run the /acs:create-flows skill for ticket EVAL-1, feature orders. Take it
all the way through: surveyed, written, reviewed, and the step finished.

I can't answer questions during this run, so here are my answers to the open
decisions -- record them as answered, don't ask me anything:
- One flow, named cancel-order, covering placed, paid and shipped orders,
  plus the order's state machine.
- If the repo wants component documents, there is one component: the orders
  module (src/shop/orders.py), documented as `orders`.
- A paid order is refunded through the payments gateway before it is marked
  cancelled; if the gateway declines the refund, the order stays paid and
  the shopper gets 502 refund_failed.
