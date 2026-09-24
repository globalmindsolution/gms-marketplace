---
description: >-
  A custom PR title format plus the convention check, from a user who is not a
  repo admin. Only the changed format is written; branch protection is
  described, never changed.
expected_outcome: >-
  settings.json holds only pr_title; the convention workflow and checker are
  installed, the tests gate is not; no branch-protection PUT; the reply names
  the required check and how to make it one.
tags: [setup]
max_turns: 30
timeout_seconds: 600
allowed_tools: [Read, Glob, Grep, Skill, Bash, Write, Edit]
---

Configure acs so our PR titles start with the ticket id in brackets, like
`[ACS-12] Add wishlist support`. Keep the branch and commit formats as they
are, and add the convention check to CI. I'm not an admin on this repo, so
don't try to change branch protection.
