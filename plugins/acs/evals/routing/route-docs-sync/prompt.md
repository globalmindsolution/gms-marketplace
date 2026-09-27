---
description: >-
  A natural-language request in the skill's domain, never naming the skill.
  It was a known confound while the prompt only presupposed a change that
  made the docs wrong: when an earlier sandbox's diff did not change
  documented behaviour, the model read it, judged the docs still accurate,
  and declined to sync -- correctly -- scoring 0.67 in the first full run.
  The prompt now states the change and the stale sentence, and a routing run
  is one turn with only the Skill tool, so the model cannot read a diff that
  says otherwise. Re-measured by the next paid run; until then its history
  is a caveat, not a baseline.
expected_outcome: Routes to acs:docs-sync.
tags: [routing, description]
max_turns: 1
allowed_tools: [Skill]
---

TKT-1's change is committed on its branch: the default page size went from 20 to 50, and the API docs still say 20. Make sure the docs match what actually changed before we raise the PR.
