---
description: >-
  /acs:set-doc-status approving one feature's documents (ADR-0130): the
  wishlist feature's living analysis (proposed v2) and its two LLD
  documents (proposed v1) move to approved in one atomic `acs.py design
  status` call that records who moved them, versions unchanged; the
  checkout feature's documents, the PRD and the HLD stay as they are, and
  nothing is committed or pushed (ADR-0127).
expected_outcome: >-
  docs/product/features/wishlist/analysis.md is approved at version 2 and
  both docs/architecture/lld/wishlist/ documents are approved at version 1,
  each with status_by and status_at in its front matter; the checkout
  analysis and LLD are still proposed; HEAD is still the scaffold's last
  commit and nothing was pushed; the reply lists the three changed files
  and points at /acs:create-pr.
tags: [behaviour]
max_turns: 40
timeout_seconds: 900
allowed_tools: [Read, Glob, Grep, Skill, Bash, AskUserQuestion]
---

Run the /acs:set-doc-status skill with the arguments `approved wishlist`. The
product council signed off on the wishlist feature today: approve all of its
documents — its analysis and its LLD. Treat this as confirmed and do not ask
me anything. Leave the checkout feature's documents, the PRD and the HLD
alone, and don't commit anything; I'll open the PR myself.
