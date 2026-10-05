---
description: >-
  /acs:analyze-requirements on a story whose second acceptance criterion
  depends on a fact nobody has decided (which accounting system finance uses,
  and so the export's file format), in a run where the user cannot answer and
  has said a guessed format is worse than none. The not-ready arm: the
  blocking question is recorded open in the clarification ledger, the analysis
  is published with ready_for_planning false, and the step stops for input
  rather than completing.
expected_outcome: >-
  docs/development/customer-listing/EVAL-1/analysis/README.md exists with ready_for_planning false in its
  front matter; clarifications.json holds an open entry; run.json records the
  analyze-requirements step interrupted with stop_reason needs_input and
  state.json ready_for_planning false; nothing under src/ or tests/ was
  created.
tags: [behaviour]
max_turns: 100
timeout_seconds: 1800
allowed_tools: [Read, Glob, Grep, Skill, Bash, Write, Edit, Agent]
---

Run the /acs:analyze-requirements skill for ticket EVAL-1 (customer export for
finance) and take it as far as it can honestly go: survey, clarification
ledger, analysis published to the run's development folder (uncommitted), and the
step finished.

I can't answer questions during this run, so don't ask me anything. And I
genuinely don't know the answer to the big one: nobody has told us which
accounting system finance uses, or what file format it imports — finance
hasn't decided. Do not guess a format; an export in the wrong format is worse
than none. For everything else, follow the repo's existing conventions. This
does not need a design.
