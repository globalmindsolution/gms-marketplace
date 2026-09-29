---
description: >-
  /acs:create-docs with the argument quality,security, where security names
  no declared doc set. parse_doc_set_arg refuses the WHOLE run (exit 2, a
  notice naming every accepted spelling): no delivery ticket is minted, the
  recognised quality set is not fanned out on its own, and no security docs
  are improvised.
expected_outcome: >-
  No ticket minted, no file created under docs/, and a reply that names
  `security` as no doc set and lists the accepted sets (quality, operations,
  principles, standards).
tags: [behaviour]
max_turns: 30
timeout_seconds: 900
allowed_tools: [Read, Glob, Grep, Skill, Bash, Write, Edit, Agent]
---

Run the /acs:create-docs skill with exactly the argument `quality,security`:
I want our test strategy and coverage policy, and a security doc set
(threat model, secrets handling) alongside it. For the quality set, the
coverage target is the PRD's 90%, measured with pytest-cov. I am not
available to answer questions: do not ask me anything.
