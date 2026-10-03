---
description: >-
  /acs:setup on a repo with a Vite front end and no .claude/launch.json,
  asked to set up the dev server the Claude Code Desktop app previews. setup
  must show the guessed server (pnpm run dev, port 5173) and write exactly
  that into .claude/launch.json through `setup apply`, put no secrets in env,
  and install no CI gate.
expected_outcome: >-
  .claude/launch.json exists with one configuration running `pnpm run dev` on
  port 5173; no env block; no CI gate installed; the reply names the server
  and its port.
tags: [behaviour]
max_turns: 40
timeout_seconds: 900
allowed_tools: [Read, Glob, Grep, Skill, Bash, Write, Edit, Agent]
---

Run the /acs:setup skill: I use the Claude Code Desktop app on this repo and
want the dev server it previews set up for the whole team, so commit the
config. Keep the ticket prefix as it is and don't add any CI check. The
detected server is right, so go with it. Don't ask me anything.
