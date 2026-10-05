---
description: >-
  /acs:review-code on a ticket whose changeset -- uncommitted on main, as
  /acs:code leaves it -- builds SQL by string formatting:
  find_customer_by_email interpolates the email into the query, an injection
  the passing test never exercises. A correct review confirms a blocking
  security finding, writes a failing verdict, and modifies nothing.
expected_outcome: >-
  verdict.json written; the kernel derives a blocking finding from it; the
  finding names the injection / missing parameter binding;
  src/shop/store.py still holds the formatted query; no new source or test
  module.
tags: [behaviour]
max_turns: 120
timeout_seconds: 2400
allowed_tools: [Read, Glob, Grep, Skill, Bash, Write, Edit, Agent]
---

Run the /acs:review-code skill on ticket EVAL-1: review EVAL-1's change, which
/acs:code left uncommitted in the working tree on main (nothing is committed
before /acs:create-pr). Review only; don't fix anything, don't run /acs:code,
and don't push. Don't ask me anything: the ticket's acceptance criteria are
the requirements, and there is no separate plan or design. Finish the review
step and tell me what you found.
