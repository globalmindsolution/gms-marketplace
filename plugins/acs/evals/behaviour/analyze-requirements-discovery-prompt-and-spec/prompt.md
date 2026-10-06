---
description: >-
  /acs:analyze-requirements in Discovery: no ticket, the requirements given as
  an attached spec (attachments/order-tracking-spec.md) plus one addition in
  the prompt (guest orders must be trackable too). The skill should take both
  containers as the run's requirements, file the analysis under the PRD's
  existing order-tracking feature, and publish the feature's LIVING analysis
  folder at docs/product/features/order-tracking/analysis/ -- versioned, with
  `feature` in place of `ticket` -- left uncommitted, without minting a ticket
  or writing a development or ticket folder.
expected_outcome: >-
  docs/product/features/order-tracking/analysis/README.md exists; its front matter
  names feature order-tracking, status proposed and version 1; it covers the
  spec's per-order opt-out and the prompt's guest orders; the run's own ledger
  and refined requirements exist under runs/<run-id>/; no ticket was minted,
  nothing was written under docs/development/ or docs/tickets/, and main is
  still checked out with nothing committed.
tags: [behaviour]
max_turns: 100
timeout_seconds: 1800
allowed_tools: [Read, Glob, Grep, Skill, Bash, Write, Edit, Agent]
---

Run the /acs:analyze-requirements skill on our order tracking feature. There is
no ticket for it yet and I don't want one created: we are still in discovery.
The requirements are the spec product attached,
attachments/order-tracking-spec.md, plus one addition of mine: guest orders
(placed without an account) must be trackable too, through the link in their
order confirmation email.

File the analysis under the PRD's existing order tracking feature, and take
it all the way through: survey, the feature's analysis published and left
uncommitted (no branch, no commit), and the step finished.

I can't answer questions during this run, so here are my answers — record
them as answered, don't ask me anything:

- Both carriers push status changes to us as signed webhooks (a shared secret
  per carrier); we never poll them.
- The statuses are label_created, in_transit, out_for_delivery, delivered and
  exception.
- Emails go through a transactional email provider we have not chosen yet;
  treat it as an outbound HTTP API.
- The spec's acceptance criteria stand as written; if you propose
  refinements, record them as proposals rather than applying them.
