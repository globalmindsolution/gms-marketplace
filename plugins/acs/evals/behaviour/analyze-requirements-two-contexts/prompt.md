---
description: >-
  /acs:analyze-requirements on a story that spans two bounded contexts -- order
  cancellation (src/shop/orders.py) and payment refunds (src/shop/payments.py)
  -- with every clarification answered up front. The analysis is a folder
  (ADR-0133): the skill should publish a README.md readable on its own, with a
  contexts table linking one plain-word kebab-case file per context, and at
  least two context files -- never one long analysis.md, never an index.md.
expected_outcome: >-
  docs/development/checkout-with-card-payments/EVAL-1/analysis/README.md exists
  with ticket EVAL-1 in its front matter, its six headings in order and a
  contexts table linking two or more context files; at least two kebab-case
  context files exist beside it and no index.md or subfolder; the result's files
  record the README and the context files; main is still checked out with
  nothing committed; the step's state.json records the run completed.
tags: [behaviour]
max_turns: 100
timeout_seconds: 1800
allowed_tools: [Read, Glob, Grep, Skill, Bash, Write, Edit, Agent]
---

Run the /acs:analyze-requirements skill for ticket EVAL-1 (refund the card
when a paid order is cancelled) and take it all the way through: survey,
analysis published to the run's development folder and left uncommitted (no
branch, no commit: /acs:create-pr commits later), and the step finished.

I can't answer questions during this run, so here are the answers to anything
you would ask me — record them as answered, don't ask me anything:

- Refunds are always for the full charge; there are no partial refunds.
- The refund is requested from the same payments gateway that took the charge,
  synchronously, when the order is cancelled.
- If the gateway declines the refund, the order stays cancelled and the failed
  refund is recorded on the order for support to follow up; nothing is retried
  automatically.
- No HTTP endpoint changes: cancellation is already exposed and keeps its
  shape.
- This does not need a design. The three acceptance criteria on the ticket are
  confirmed as written; if you propose a refinement, record it as a proposal
  rather than applying it.
