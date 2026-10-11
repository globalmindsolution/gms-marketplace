---
description: >-
  Setup with the document templates scaffolded (ADR-0148): keep the default
  ticket prefix, no CI, no model settings, but copy acs's templates into the
  repo so the team can edit them. Setup should copy every built-in template
  into .acs/templates/ with its lock file, without asking.
expected_outcome: >-
  .acs/templates/ holds the PRD, feature PRD, PR, ticket, tech-design and
  audit-report templates plus templates.lock.json recording each one's
  built-in hash; no CI installed; the reply lists them for the commit.
tags: [setup]
max_turns: 30
timeout_seconds: 600
allowed_tools: [Read, Glob, Grep, Skill, Bash, Write, Edit]
---

Set up acs in this repo. Keep the default ticket prefix, don't scaffold the
model settings and don't install any CI checks -- but do copy acs's document
templates into the repo; we want to edit them ourselves.
