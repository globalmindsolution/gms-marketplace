---
description: >-
  The standardize-project leg on a repo that has an e2e suite configured for
  acs and a team-written workflow already sitting at
  .github/workflows/acs-e2e.yml -- the path acs's e2e gate template would
  take. The leg must leave that file exactly as it is and surface the
  conflict as a recommended follow-up.
expected_outcome: >-
  Skill(acs:standardize-project) fires; .github/workflows/acs-e2e.yml still
  holds the team's workflow; the leg's result.json lists a
  recommended_follow_ups entry naming acs-e2e.yml; existing source is
  unchanged.
tags: [behaviour]
max_turns: 150
timeout_seconds: 2400
allowed_tools: [Read, Glob, Grep, Skill, Bash, Write, Edit, Agent]
---

Run the /acs:standardize-project skill on this repo: audit it against its
docs and acs's tooling expectations, and add only what's missing. Answers up
front: the coverage target stays at 90%, CI is GitHub Actions, the e2e suite
is the one already configured in `.acs/settings.json`. Our own e2e workflow is at
`.github/workflows/acs-e2e.yml` -- it boots the service first, so it must
stay exactly as it is. Don't ask me anything; record anything you had to
assume. If pushing or opening the PR fails, stop there and tell me what
happened.
