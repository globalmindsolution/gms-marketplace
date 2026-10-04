---
description: >-
  /acs:create-flows on a story (EVAL-1, feature orders) that lets a shopper
  cancel an order before it ships, refunding a paid one through the
  payments gateway, in a repo whose orders code moves an order placed ->
  paid -> shipped -> delivered and whose design.lld_types is the default
  (components off). It should write the cancel-order flow (sequence, and an
  activity for the branching) and the order's state machine under
  lld/orders/flows/, each versioned through acs.py design, with the cancel
  message's state change present as placed -> cancelled and paid ->
  cancelled and nothing from shipped; write nothing under components/ and
  no code; record the written paths in states.files; and finish through its
  post-hook -- without asking anything.
expected_outcome: >-
  docs/architecture/lld/orders/flows/cancel-order.md has version front
  matter (proposed, EVAL-1, orders), Purpose/Trigger/Participants/Sequence
  .../Errors and edge cases in order, and a sequenceDiagram carrying the
  cancel request and the refund call; flows/state-order.md has front
  matter, Entity/States/Transitions/Invariants and a stateDiagram-v2 with
  placed --> cancelled and paid --> cancelled labelled with the cancel
  request and no shipped or delivered --> cancelled; nothing is created
  under components/, outside lld/orders/flows/ (bar the feature README), or
  as code; the step's state.json is completed with both files in
  states.files.
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
- A paid order is refunded through the payments gateway before it is marked
  cancelled; if the gateway declines the refund, the order stays paid and
  the shopper gets 502 refund_failed.
- Cancelling an order that is already cancelled returns 409
  order_not_cancellable.
