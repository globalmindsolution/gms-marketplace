---
description: >-
  Setup re-run on a repo whose team edited a scaffolded template (ADR-0148):
  the feature PRD template gained a Rollout section. The re-run must keep the
  edit -- an edited copy is the team's -- and report it as customised.
expected_outcome: >-
  .acs/templates/prd-feature-default.md still carries its ## Rollout section;
  the custom ticket prefix survives; the reply names the template as kept
  (customised).
tags: [setup]
max_turns: 30
timeout_seconds: 600
allowed_tools: [Read, Glob, Grep, Skill, Bash, Write, Edit]
---

I set acs up here a while ago, templates included, and we've since changed our
feature PRD template. Run setup again to make sure everything is in place --
don't change anything I configured.
