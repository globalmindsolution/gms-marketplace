---
description: >-
  /acs:set-doc-status deprecating a cut feature with a reason (ADR-0130):
  the gift-cards analysis and its two LLD documents, all approved, move to
  deprecated in one atomic `acs.py design status` call that records the
  reason as status_reason, versions unchanged; the wishlist LLD, the PRD and
  the HLD stay as they are, and nothing is committed or pushed (ADR-0127).
expected_outcome: >-
  docs/product/features/gift-cards/analysis.md and both
  docs/architecture/lld/gift-cards/ documents read status deprecated at
  version 1 with status_reason naming the leadership cut; the wishlist LLD
  is still approved; HEAD is still the scaffold's last commit and nothing
  was pushed; the reply lists the three changed files and points at
  /acs:create-pr.
tags: [behaviour]
max_turns: 40
timeout_seconds: 900
allowed_tools: [Read, Glob, Grep, Skill, Bash, AskUserQuestion]
---

Run the /acs:set-doc-status skill. Leadership cut gift cards from the
product this week, so deprecate every gift-cards document — its analysis and
its LLD — with the reason "Gift cards cut from scope by leadership
(2026-10)". Treat this as confirmed and do not ask me anything. The wishlist
documents, the PRD and the HLD stay as they are, and don't commit anything.
