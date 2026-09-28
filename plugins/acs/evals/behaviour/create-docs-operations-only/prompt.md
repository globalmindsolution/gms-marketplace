---
description: >-
  /acs:create-docs asked for just the operations set, on a repo whose PRD sets
  99.9% availability and a 300 ms p95, with the release, on-call and
  scheduling facts supplied up front. It should mint one delivery ticket,
  write the five docs/operations/ files tailored to those facts, push the
  set's delivery branch to origin, and report the failed gh PR step as a
  finding.
expected_outcome: >-
  The five docs/operations/ files exist with their required sections;
  observability.md states the 99.9% and 300 ms targets, runbooks.md the
  15-minute escalation, test-scheduling.md the 02:00 UTC schedule and
  release-process.md the CHANGELOG.md discipline; no other doc set written; a
  task/EVAL-1-* branch pushed with upstream set; result.json records the gh
  failure and no PR.
tags: [behaviour]
max_turns: 150
timeout_seconds: 3000
allowed_tools: [Read, Glob, Grep, Skill, Bash, Write, Edit, Agent]
---

Run the /acs:create-docs skill for just the `operations` set: I want the
release process, runbooks, observability, incident response and test
scheduling docs for this repo, nothing else. Treat these as confirmed and do
not ask me anything:

- Only the operations set. Do not start quality, principles or standards.
- Releases: semantic versions cut from `main` and tagged `vX.Y.Z` (the
  current release is v2.4.0); every change adds a line to `CHANGELOG.md` in
  the same PR, promoted to a dated section at release time. Roll back by
  redeploying the previous tag.
- On-call: one weekly rotation; if the on-call engineer has not acknowledged
  a page within 15 minutes it escalates to the tech lead.
- Observability: JSON logs to stdout (as the deployment view says); the SLOs
  are the PRD's, 99.9% monthly availability and p95 API latency under 300 ms,
  and an alert fires when either is breached over one hour.
- Incidents: three severities, SEV1 (checkout down) to SEV3 (cosmetic); a
  postmortem is required for every SEV1 within five working days.
- Test scheduling: run /acs:test headless every night at 02:00 UTC from cron
  on the build host; there is no CI configuration in the repo yet.

Pushing to origin works from this machine, but there is no GitHub access
here: when a gh call fails, handle it the way the skill says to, and finish.
