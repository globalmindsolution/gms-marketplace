---
description: >-
  A greenfield repo holding only a PRD and an approved architecture set (with
  hld/tech-stack.md). /acs:project must detect bootstrap mode and dispatch the
  create-project leg, which scaffolds the Python skeleton the tech stack pins
  -- build manifest with a coverage floor, a smoke test, CI -- and records its
  result on its own delivery ticket.
expected_outcome: >-
  Skill(acs:create-project) fires (via /acs:project); pyproject.toml is created
  with a 90% coverage floor; a CI workflow and a test file are created; the
  delivery ticket's steps/create-project/result.json is written. Opening the
  PR fails (no forge in an eval run) and is reported, not routed around.
tags: [behaviour]
max_turns: 150
timeout_seconds: 2400
allowed_tools: [Read, Glob, Grep, Skill, Bash, Write, Edit, Agent]
---

Run the /acs:project skill on this repo. It's a brand-new product repo: all
we have so far is the PRD and the approved architecture docs under `docs/`,
including `docs/architecture/hld/tech-stack.md`, and no code at all. Scaffold
the project skeleton exactly as the tech stack says: Python 3.11, a
`pyproject.toml`, pytest with pytest-cov failing below our 90% coverage target,
ruff, pre-commit, one GitHub Actions workflow, and the `GET /health` smoke
slice. We don't want an e2e harness yet. Everything you'd need to decide is in the architecture docs or this
message, so don't ask me anything -- if something is still open, pick the
option the tech stack points to and record it as an assumption. If pushing or
opening the PR fails, stop there and tell me what happened.
