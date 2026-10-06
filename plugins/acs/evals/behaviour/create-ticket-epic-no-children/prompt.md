---
description: >-
  /acs:create-ticket on a raw request that is plainly an epic (order tracking,
  PRD feature F3), with every record decision delegated up front. The skill
  should mint ONE ticket typed epic with no design flag (ADR-0139), drafted by
  the epic author and checked by the reviewer, its title
  rendered through the epic title format, children left empty for a later
  /acs:breakdown-ticket run, the PRD trace recorded, and close its step
  -- without asking anything and without minting any child.
expected_outcome: >-
  The minted ticket.json is type epic with no needs_design key, children []
  and a title starting [EPIC]; no second ticket partition exists; the create-ticket
  step state records completed with a prd_trace naming F3 / order tracking.
tags: [behaviour]
max_turns: 100
timeout_seconds: 1800
allowed_tools: [Read, Glob, Grep, Skill, Bash, Write, Edit, Agent]
---

Run the /acs:create-ticket skill with this request:

Order tracking for shoppers (PRD feature F3): shoppers can see where their
order is from payment to delivery. It spans carrier status updates coming in
from our shipping carriers, an order status page, and an email to the shopper
on every status change. This is an EPIC — it is far too big for one pull
request.

I can't answer questions during this run, so don't ask me anything. Use your
judgement for the rest of the record — title, description, priority and the
epic's acceptance criteria are yours to decide, no need to confirm them — and
there is no due date. Do not break it into child tickets now; that happens
later. Take the skill all the way through: ticket written and the
step finished.
