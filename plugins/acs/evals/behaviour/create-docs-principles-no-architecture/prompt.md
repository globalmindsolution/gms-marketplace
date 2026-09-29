---
description: >-
  /acs:create-docs asked for just the principles set on a repo with a PRD
  and no architecture doc set, the stack and the principles confirmed up
  front. It should not refuse or stop for the missing architecture set: it
  should mint one delivery ticket, write docs/principles/principles.md with
  the confirmed principles and their rationale, record that no architecture
  set exists, push the delivery branch, and report the failed gh PR step.
expected_outcome: >-
  docs/principles/principles.md with Principles and Rationale sections
  stating the three confirmed principles; the authoring notes record the
  missing architecture set; no architecture or other doc set written; a
  task/EVAL-1-* branch pushed with upstream set; result.json records the gh
  failure and no PR.
tags: [behaviour]
max_turns: 120
timeout_seconds: 2400
allowed_tools: [Read, Glob, Grep, Skill, Bash, Write, Edit, Agent]
---

Run the /acs:create-docs skill for just the `principles` set: I want this
repo's engineering principles written down, nothing else. There is no
architecture doc set yet and I do not want one written now. Everything the
skill would otherwise confirm with me is answered below; treat it as
confirmed and do not ask me anything:

- Only the principles set. Do not start quality, operations or standards,
  and do not write architecture docs.
- Stack (in place of an architecture set): one Python 3.12 service, package
  `shop` in a src layout, deployed as a single container; card payments will
  go only through an external payments gateway.
- The principles, exactly three:
  1. Never store card data: card details go straight to the payments gateway
     and never touch our database or logs.
  2. Standard library first: add a third-party dependency only when the
     standard library cannot do the job, and say why in the PR.
  3. Every change ships with tests: unit coverage stays at or above 90%, the
     PRD's floor.

Pushing to origin works from this machine, but there is no GitHub access
here: when a gh call fails, handle it the way the skill says to, and finish.
