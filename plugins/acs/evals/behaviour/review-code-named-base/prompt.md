---
description: >-
  /acs:review-code against a named base ref other than main: EVAL-1's branch is
  stacked on release/2.4, whose own commit (a hard-coded export token) was
  reviewed separately. Reviewed with base release/2.4, the changeset is the
  ticket's age check alone, whose boundary defect (age > 18) must be a
  confirmed blocking finding -- and the release branch's file must not appear
  in the verdict.
expected_outcome: >-
  verdict.json written; the kernel derives a blocking finding; the finding
  names the 18-year boundary in can_checkout; the verdict never mentions
  src/shop/export.py or its token; nothing is changed.
tags: [behaviour]
max_turns: 120
timeout_seconds: 2400
allowed_tools: [Read, Glob, Grep, Skill, Bash, Write, Edit, Agent]
---

Run the /acs:review-code skill on ticket EVAL-1 with release/2.4 as the base:
the ticket branch that is checked out now is stacked on release/2.4, whose own
changes were reviewed separately, so review only what this branch adds on top
of release/2.4 -- not the diff against main. Review only; don't fix anything,
don't run /acs:code, and don't push. Don't ask me anything: the ticket's
acceptance criteria are the requirements, and there is no separate plan or
design. Finish the review step and tell me what you found.
