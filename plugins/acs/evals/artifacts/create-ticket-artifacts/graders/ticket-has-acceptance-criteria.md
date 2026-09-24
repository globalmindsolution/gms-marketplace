---
type: regex
target: { source: file, path: .acs/state-machine/example-shop/EVAL-1/ticket.json }
pattern: '"acceptance_criteria"\s*:\s*\[\s*"'
---

The ticket carries at least one acceptance criterion. `acs step start
--allocate`, the skill's mandatory first action, mints EVAL-1 with a
placeholder ticket.json whose `acceptance_criteria` is `[]` -- and whose id,
type (`--type task`) and `needs_design: false` already satisfy the three
graders above. Without this grader and the title one, a run that started the
skill and then wrote nothing would pass. The grader calibration test
(tests/acs/test_eval_grader_calibration.py) plays exactly that run.
