---
description: >-
  The create-project leg named directly on an EXISTING Python codebase. Its
  greenfield gate must refuse: result.json `failed` with a `greenfield`
  finding and all scaffold booleans false, no scaffold written, existing
  source and pyproject.toml untouched, and a reply pointing at the ticket
  pipeline instead.
expected_outcome: >-
  Skill(acs:create-project) fires; steps/create-project/result.json carries
  the greenfield finding; no CI, pre-commit or coverage file is created;
  src/shop/__init__.py and pyproject.toml read as before.
tags: [behaviour]
max_turns: 60
timeout_seconds: 1200
allowed_tools: [Read, Glob, Grep, Skill, Bash, Write, Edit, Agent]
---

Run the /acs:create-project skill itself on this repo -- not /acs:project --
and scaffold the project skeleton from the tech stack in
`docs/architecture/hld/tech-stack.md`: pytest with coverage failing below
90%, ruff, pre-commit and a GitHub Actions workflow. No e2e harness. Don't ask me anything. If it refuses, don't work
around it or switch to another skill: tell me why and what to do instead.
