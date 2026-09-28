---
description: >-
  /acs:project on a greenfield repo whose docs/architecture/ has a C4 context
  view but no hld/tech-stack.md. create-project must take its
  No-architecture fallback -- not stop -- record the stack, layout and
  coverage answers the prompt relays as create-project clarifications before
  scaffolding, and scaffold from them without writing an architecture doc
  itself.
expected_outcome: >-
  Skill(acs:create-project) fires (via /acs:project); EVAL-1's
  clarifications.json holds create-project entries naming the Python stack;
  pyproject.toml is created with a 90% coverage floor; the leg writes its
  result.json; nothing new under docs/. Opening the PR fails (no forge) and
  is reported.
tags: [behaviour]
max_turns: 150
timeout_seconds: 2400
allowed_tools: [Read, Glob, Grep, Skill, Bash, Write, Edit, Agent]
---

Run the /acs:project skill on this repo. It's a brand-new product with no
code yet. We haven't written a tech-stack doc, so here are the answers to
the stack, layout and tooling questions it will have -- use them as my
answers and don't ask me anything:

- Stack: Python 3.11, packaged with a `pyproject.toml` (setuptools), no web
  framework (standard library `http.server`).
- Layout: the package in `src/shop/`, unit tests in `tests/`.
- Tests and coverage: pytest with pytest-cov, failing below our 90% target.
- Lint/format: ruff, plus a pre-commit config running it.
- CI: one GitHub Actions workflow running install, lint and tests with
  coverage.
- No e2e harness. The first slice is `GET /health` returning `ok`.
- Keep the default branch and commit formats.

Don't write the architecture docs yourself. If pushing or opening the PR
fails, stop there and tell me what happened.
