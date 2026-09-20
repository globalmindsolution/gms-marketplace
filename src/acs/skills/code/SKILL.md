---
name: code
description: Implement an approved implementation plan in the consumer repo using TDD, targeted tests only. Dispatches to the delivery-path leg the plan recorded — code-trivial, code-small, code-standard or code-complex. The changeset review is a separate step, /acs:review-code. Takes a ticket id, a prompt or a document.
argument-hint: "[ticket-id | prompt | document]"
disallowed-tools: Edit, NotebookEdit
---

You are the entry point of /acs:code. You do not implement anything yourself:
you resolve which **delivery path** this change is on and invoke that path's
leg, which is the coordinator for the run.

**You have no verifier.** The changeset review is `/acs:review-code`, a step of
its own. That is the crux of this redesign: an implementer that grades its own
output ran the full unit suite inside an iteration that might be discarded, and
gave per-finding adjudication to only one of four paths. Do not spawn a
verifier, do not judge the changeset, and do not run the full suite — write the
tests your change touches and stop.

Four legs implement this step:

| Path | Leg | Executors | Plan approval |
|---|---|---|---|
| `trivial` | `acs:code-trivial` | one, always | not required |
| `small` | `acs:code-small` | one, rarely two | not required |
| `standard` | `acs:code-standard` | one per disjoint file-map partition | **enforced** |
| `complex` | `acs:code-complex` | one per partition **+ an integration executor** | **enforced** |

The two axes the legs used to differ by are gone, and both left for the same
reason — they were review properties, not implementation properties. The
verifier's shape is `/acs:review-code`'s business on every run, and the
iteration ceiling is the workflow's `loops[].max_iterations`.

**The path is judged once, by the plan, and recorded in it.** It is not an
option, not an argument, and not yours to choose. `/acs:create-impl-plan`
judges it from the plan's own scope and writes it to the plan's `## Contract`
block; every later read — including this one — takes that value. That is what
keeps a resumed run on the path its first session chose rather than splitting
one pipeline across two.

## Resolve the path

```bash
python3 - <<'PY'
import json, os, sys
sys.path.insert(0, os.path.join(os.environ["CLAUDE_PLUGIN_ROOT"], "hooks", "scripts"))
import acs_lib as lib
from acs_lib import plan_contract

cwd = os.getcwd()
try:
    ctx = lib.build_context(cwd)
    run_id = lib.current_run_id(ctx)
    rdir = lib.run_dir(lib.repo_dir(ctx["workspace"], ctx["repo_id"]), run_id)
    plan = os.path.join(rdir, "steps", "create-impl-plan", "plan.md")
    contract = plan_contract.read(plan)
    print(json.dumps({
        "run_id": run_id,
        "plan": plan if os.path.isfile(plan) else None,
        "delivery_path": plan_contract.delivery_path(contract),
    }, indent=2))
except lib.GateError as exc:
    sys.stderr.write("acs code: %s\n" % exc)
    sys.exit(2)
PY
```

On exit 2: surface stderr verbatim and stop.

**A recorded `delivery_path`** → invoke that leg with the Skill tool and follow
it to completion as its coordinator:

| Recorded path | Invoke |
|---|---|
| `trivial` | `Skill(acs:code-trivial)` |
| `small` | `Skill(acs:code-small)` |
| `standard` | `Skill(acs:code-standard)` |
| `complex` | `Skill(acs:code-complex)` |

It is a real Skill call, so the leg's own pre-hook gates it (through `code`'s
gate) and its own post-hook finalises it. You add nothing: no extra context, no
instructions of your own, no interpretation of the plan.

**No plan at all** → you were invoked standalone, on a subject rather than
after `/acs:create-impl-plan` (§3.11). Derive an **implicit plan** from your own
read-only survey of the repo and the subject, then judge its path with
`${CLAUDE_PLUGIN_ROOT}/skills/code/references/classify.md`.

> **The implicit plan is for the cheap paths only.** If your survey judges the
> work `standard` or `complex`, stop with `stop_reason: needs_input` and say:
> *this needs a plan and an approval — run `/acs:create-impl-plan`*. Plan
> approval is a real brake, and a plan you wrote for yourself and then approved
> by implementing is not an approval. `--plan <file>` supplies one instead.

**No recorded path but a plan exists** → the plan predates the `## Contract`
block. Judge the path yourself with the rubric above, and say in your handoff
that you did and why, so the next reader knows it was not the plan's own
judgement.

## What you must not do

- **Never implement.** If you find yourself reading a spec or editing a source
  file, you have taken the leg's job. Dispatch and follow.
- **Never review.** No verifier, no lenses, no full suite. The review is step 6
  and it reviews you.
- **Never run the full test suite.** Targeted tests only — the tests your
  change touches. `/acs:review-code`'s final gate runs the suite once, last,
  exactly when it counts, and that is what makes this discipline safe.
- **Never pick a path to suit the work you expect.** A plan that looks bigger
  than its recorded path is a finding for `/acs:review-code` to raise, and
  `stop_reason: plan_superseded` is the remedy — it re-runs
  `/acs:create-impl-plan` and re-judges from the corrected plan.
- **Never pass a path as an argument.** A second token naming a path is
  refused: the path is judged from the plan.
- **Never run two legs for one run.** They share `steps/code/` and its
  `state.json`; a second leg would write over the first one's iteration
  artifacts.

## On iteration 2+

The loop sent the cursor back here because `/acs:review-code` recorded
`blocking_findings`. Read `steps/review-code/verdict.json` and nothing else
from the review — not the lens reports, not the adjudication transcripts. Every
**confirmed** finding must be answered by id in your `result.json`:

- `fixed` — naming the commit, and for a behavioural finding the test you wrote
  first. TDD holds inside the loop.
- `disputed` — with the evidence that defeats the claim. This is not a way out:
  the next adjudicator receives your dispute and rules again, and a finding
  disputed then confirmed a second time stops the run for a human rather than
  spending the last iteration on the same argument.

Each finding carries a `resolved_when` — what the fix must make true. Work to
that, not to your own reading of the claim.

## Finish

The leg ran `acs step start --step code` and `post-code.py`, wrote every
artifact under `steps/code/`, and produced the completion report. Relay its
handoff unchanged, and add one line naming the path and why:

> Delivery path: **`<path>`** — `<the plan's recorded reason>`
