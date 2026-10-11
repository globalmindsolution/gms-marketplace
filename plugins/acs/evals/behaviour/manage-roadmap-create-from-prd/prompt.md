---
description: >-
  /acs:manage-roadmap create mode: an approved PRD hub with four feature PRDs
  and no roadmap. Every planning choice is given in the prompt, since the run
  cannot answer questions. It should write docs/product/roadmap.md in the
  skill's shape -- three milestones, each with its release version, linked
  feature PRDs and `none yet` epics, every status derived (`planned`, no
  tickets exist), and a Release versions table with one row per milestone --
  give it its first version front matter, leave the PRD untouched, and leave
  the roadmap as an uncommitted local change listed in states.files -- no
  ticket, branch, commit, push or PR (ADR-0127, ADR-0145).
expected_outcome: >-
  docs/product/roadmap.md with Storefront v2.4.0, Checkout v2.5.0 and Order
  tracking v2.6.0, each linking its feature PRD and `planned`, a Release
  versions table mapping each version to its milestone, and version front
  matter at status proposed, version 1; prd.md still approved v1; HEAD still
  the scaffold's commit on main and nothing pushed; the step finished with
  the roadmap in states.files and no PR.
tags: [behaviour]
max_turns: 150
timeout_seconds: 2400
allowed_tools: [Read, Glob, Grep, Skill, Bash, Write, Edit, Agent]
---

Run the /acs:manage-roadmap skill to plan the first roadmap for this repo from
the PRD in docs/product. Everything the skill would ask me is answered below.
Treat all of it as confirmed and do not ask me anything.

- Milestone "Storefront" ships customer listing in release v2.4.0.
- Milestone "Checkout" ships card checkout in release v2.5.0.
- Milestone "Order tracking" ships order tracking in release v2.6.0.
- Saved carts (a Could-have) is not scheduled yet.
- No epics exist yet, and there are no target dates.
