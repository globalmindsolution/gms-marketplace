---
name: code
description: Implement a ticket's approved implementation plan in the consumer repo using TDD on a dedicated branch, with a built-in changeset review loop. Requires plan.md from /acs:create-impl-plan. Dispatches to the delivery-path leg the ticket was judged onto — code-trivial, code-small, code-standard or code-complex. Use when a ticket has a plan and is ready to be implemented, before /acs:create-pr.
argument-hint: "[ticket-id]"
disallowed-tools: Edit, NotebookEdit
---

You are the entry point of /acs:code. You do not implement anything yourself:
you resolve which **delivery path** this ticket is on and invoke that path's
leg, which is the coordinator for the run.

Four legs implement this step (ADR-0095):

| Path | Leg | Machinery |
|---|---|---|
| `trivial` | `acs:code-trivial` | one executor, one verifier pass, ceiling 2 |
| `small` | `acs:code-small` | one executor, one verifier pass, ceiling 2 |
| `standard` | `acs:code-standard` | parallel executors, one verifier pass over all 16 dimensions, ceiling 3, plan approval enforced |
| `complex` | `acs:code-complex` | parallel executors, four merged verifier lenses, ceiling 3, plan approval enforced |

**The path is judged once, from the plan, and recorded.** It is not an option,
not an argument, and not yours to choose. `/acs:ship` judges it after
`/acs:create-impl-plan` completes and writes `delivery_path` to
`pipeline-state.json`; every later read — including this one — takes the
recorded value. That is what keeps a resumed run on the path its first session
chose rather than splitting a pipeline across two.

## Resolve the path

Run exactly (the heredoc terminator `PY` must stay at column 0):

```bash
python3 - "$ARGUMENTS" <<'PY'
import json, os, sys
sys.path.insert(0, os.path.join(os.environ["CLAUDE_PLUGIN_ROOT"], "hooks", "scripts"))
import acs_lib as lib
from acs_lib import workflow

arg = (sys.argv[1] if len(sys.argv) > 1 else "").strip()
cwd = os.getcwd()
try:
    ctx = lib.build_context(cwd)
    ticket_id = arg.split()[0] if arg else ""
    if not ticket_id:
        sys.stderr.write("acs code: which ticket? pass a ticket id.\n")
        sys.exit(2)
    tdir, _archived = lib.find_ticket_partition(ctx["workspace"], ctx["repo_id"], ticket_id)
    if not tdir:
        sys.stderr.write("acs code: no partition for %s — run /acs:create-ticket first.\n" % ticket_id)
        sys.exit(2)
    resolved = workflow.resolve_workflow(ctx.get("checkout_root"))
    doc = workflow.validate_workflow_file(resolved["path"])
    print(json.dumps({
        "ticket_id": ticket_id,
        "delivery_path": workflow.recorded_delivery_path(tdir, ticket_id),
        "reason": workflow.recorded_delivery_reason(tdir, ticket_id),
        "paths": workflow.declared_paths(doc),
        "classify_after": (workflow.delivery_of(doc) or {}).get("classify_after"),
    }, indent=2))
except lib.GateError as exc:
    sys.stderr.write("acs code: %s\n" % exc)
    sys.exit(2)
PY
```

On exit 2: surface stderr verbatim and stop.

**A recorded `delivery_path`** → invoke that leg with the Skill tool,
`acs:code-<path>`, passing the ticket id as its argument, and follow it to
completion as its coordinator. You add nothing: no extra context, no
instructions of your own, no interpretation of the plan. The leg runs its own
Start, holds its own reflection loop, and returns its own handoff — which is
this skill's handoff too.

**No recorded path** → the ticket reached `/acs:code` without passing through
`/acs:ship`'s classification. Judge it yourself, here, using the rubric in
`${CLAUDE_PLUGIN_ROOT}/skills/code/references/classify.md`, then record it
before dispatching:

```bash
python3 - "<ticket-id>" "<path>" "<one sentence of reason>" <<'PY'
import os, sys
sys.path.insert(0, os.path.join(os.environ["CLAUDE_PLUGIN_ROOT"], "hooks", "scripts"))
import acs_lib as lib
from acs_lib import workflow
ctx = lib.build_context(os.getcwd())
tdir, _ = lib.find_ticket_partition(ctx["workspace"], ctx["repo_id"], sys.argv[1])
doc = workflow.validate_workflow_file(workflow.resolve_workflow(ctx.get("checkout_root"))["path"])
workflow.record_delivery_path(tdir, sys.argv[1], sys.argv[2], sys.argv[3], doc=doc)
print("recorded %s: %s" % (sys.argv[1], sys.argv[2]))
PY
```

Recording it is not bookkeeping. It is what makes a direct `/acs:code` run and
a later `/acs:ship <id>` agree about which path the ticket is on, and it is why
`record_delivery_path` refuses to move a ticket already on one.

**The workflow declares no `delivery` block** (a consumer override that
predates paths, or one that deliberately has none) → `paths` comes back empty.
Run `acs:code-standard`: it is the path whose rigor matches the single `code`
protocol this plugin had before the split, so a workflow with no opinion gets
the behaviour it used to have.

## What you must not do

- **Never implement.** If you find yourself reading a spec or editing a source
  file, you have taken the leg's job. Dispatch and follow.
- **Never pick a path to suit the work you expect.** A plan that looks bigger
  than its recorded path is the **Path audit** dimension's finding to raise,
  and `stop_reason: plan_superseded` is the remedy — it re-runs
  `/acs:create-impl-plan` and re-classifies from the corrected plan.
- **Never pass a path as an argument.** `$ARGUMENTS` is a ticket id. A second
  token naming a path is refused: say that the path is judged from the plan,
  and point at `/acs:create-impl-plan` for work whose plan no longer fits.
- **Never run two legs for one ticket.** They share `phases/code/` and
  `code-state.json`; a second leg would write over the first one's iteration
  artifacts.

## Finish

The leg ran `skill-start.py --skill code` and `post-code.py`, wrote every phase
artifact under `<partition>/phases/code/`, and produced the completion report.
Relay its handoff unchanged, and add one line naming the path and why:

> Delivery path: **`<path>`** — `<the recorded reason>`
