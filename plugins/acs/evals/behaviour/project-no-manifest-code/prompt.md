---
description: >-
  /acs:project on an existing Python codebase that has source, tests and a
  requirements.txt but none of the declared evidence rows (no pyproject.toml,
  setup.py, pre-commit or coverage config). The evidence table says
  bootstrap, so the umbrella dispatches create-project -- and that leg's own
  greenfield gate refuses. The umbrella must report the refusal and stop,
  never re-dispatch to standardize-project and never scaffold over the code.
expected_outcome: >-
  Skill(acs:project) fires; create-project's result.json records the
  greenfield refusal (a `greenfield` finding); no standardize-project step
  exists; no manifest, CI, pre-commit or coverage file is created;
  app/__init__.py is unchanged; the reply says why it stopped.
tags: [behaviour]
max_turns: 80
timeout_seconds: 1800
allowed_tools: [Read, Glob, Grep, Skill, Bash, Write, Edit, Agent]
---

Run the /acs:project skill on this repo so its structure and tooling match
what acs expects. Answers to anything it might ask: the coverage target
stays at 90%, CI is GitHub Actions, we don't want an e2e suite, and keep the
default branch and commit formats. Don't ask me anything -- decide from the
repo and this message. If a step refuses, don't work around it: stop and
tell me what refused, why, and what I should do next.
