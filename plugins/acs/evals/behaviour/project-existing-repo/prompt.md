---
description: >-
  /acs:project on an existing Python codebase (pyproject.toml, src/, tests/)
  that lacks CI, pre-commit and coverage config. The umbrella must read its
  evidence table, state standardize mode with pyproject.toml as the evidence,
  and dispatch the standardize-project leg -- never create-project.
expected_outcome: >-
  Skill(acs:project) fires; the leg allocates its "Brownfield project
  standardization" delivery ticket (EVAL-1) and writes its result.json; no
  create-project step exists; existing source is untouched; the reply names
  the mode and the pyproject.toml evidence.
tags: [behaviour]
max_turns: 150
timeout_seconds: 2400
allowed_tools: [Read, Glob, Grep, Skill, Bash, Write, Edit, Agent]
---

Run the /acs:project skill on this repo. We want its structure and tooling
brought up to what acs expects before we start using the ticket pipeline.
Answers to anything it might ask: the coverage target stays at 90%, we don't
want an e2e suite, CI is GitHub Actions, and keep the default branch and
commit formats. Don't ask me anything -- decide from the repo and this
message, and record anything you had to assume. If pushing or opening the PR
fails, stop there and tell me what happened. In your final message, tell me
which mode you picked and what on disk decided it.
