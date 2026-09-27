---
description: >-
  A plain description of the leg's own subject must NOT reach the leg:
  /acs:project is the documented front door and is what should pick it up.
  What delivers that is the leg's DESCRIPTION ("Internal leg of
  /acs:project, not a user-facing command"), not a frontmatter flag. Until
  2026-09-13 the leg set disable-model-invocation, which the CLI enforces by
  refusing the Skill call — and /acs:project dispatches this leg with a real
  Skill(acs:standardize-project) call, so the flag stopped the fold working
  at all. The probe is unchanged; only its justification is.
expected_outcome: Does not invoke acs:standardize-project.
tags: [routing, negative]
max_turns: 1
allowed_tools: [Skill]
---

Audit this existing repo against our standards and scaffold whatever tooling is missing.
