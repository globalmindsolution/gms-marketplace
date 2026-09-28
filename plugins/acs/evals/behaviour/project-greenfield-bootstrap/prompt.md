---
description: >-
  /acs:project on a greenfield repo (README, LICENSE, CLAUDE.md, a PRD and an
  approved architecture set with hld/tech-stack.md, no code). The umbrella
  must report bootstrap mode -- no build manifest found -- and dispatch the
  create-project leg, never standardize-project; what the leg leaves behind
  shows which one ran.
expected_outcome: >-
  Skill(acs:project) fires; the create-project leg allocates its "Project
  scaffold" delivery ticket (EVAL-1), creates pyproject.toml and writes its
  result.json; no standardize-project step exists; the reply names bootstrap
  mode and create-project. Opening the PR fails (no forge) and is reported.
tags: [behaviour]
max_turns: 150
timeout_seconds: 2400
allowed_tools: [Read, Glob, Grep, Skill, Bash, Write, Edit, Agent]
---

Run the /acs:project skill on this repo. It's a new product: we only have
the PRD and the approved architecture docs so far, and the stack is pinned in
`docs/architecture/hld/tech-stack.md`. Answers to anything it might ask: the
coverage target stays at 90%, we don't want an e2e harness yet, CI is GitHub
Actions, and keep the default branch and commit formats. Don't ask me
anything -- decide from the repo and this message, and record anything you
had to assume. If pushing or opening the PR fails, stop there and tell me
what happened. In your final message, tell me which mode you picked and what
on disk decided it.
