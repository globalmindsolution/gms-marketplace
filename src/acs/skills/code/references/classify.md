# Judging a plan onto a delivery path

*Read by `/acs:ship` after `delivery.classify_after` completes, and by
`/acs:code` when a ticket reaches it with no path recorded. Path:*
*`${CLAUDE_PLUGIN_ROOT}/skills/code/references/classify.md`.*

The four paths are `trivial`, `small`, `standard` and `complex`. Exactly one is
chosen, once, from `plan.md`, and recorded with the reason on
`run.json`. Everything downstream reads that record; nothing
re-judges (ADR-0095).

## Why this is a judgement and not a score

The obvious implementation is a threshold over counts — files touched, specs,
risks — and it would be wrong in both directions on the first two tickets it
saw. Twelve files of mechanical rename is smaller work than one file of new
session handling. A plan with three risks listed may be safer than one with
none, because someone thought about it.

So read the plan and decide. What makes that accountable is not a formula but
the record: one of four values, and a sentence saying what in the plan decided
it. A reviewer can check that sentence against the diff, and the review's
**Path audit** dimension does exactly that on every iteration.

## What to read

Read `plan.md` — and only `plan.md`, plus the ticket document you already
have. Not the diff (there isn't one), not the specs, not the repo. Four of its
sections carry the signal:

- **Executor tasks & file map** — how many files, and are they one coherent
  group or several that must be coordinated? *What* the files are matters more
  than how many: a migration, an auth path, a payment path, a public API, a
  hook that gates other work, anything the repo's own docs call load-bearing.
- **Test strategy** — new suites, or new cases in existing ones? A plan that
  needs a new kind of test is describing new behaviour.
- **Risks** — what the planner thought could go wrong, in its own words. A
  risk about data loss, a security boundary or a migration is worth more than
  three about naming.
- **API/data changes** — a changed public surface or stored shape is the
  single strongest signal, because it is the one whose blast radius extends
  past this ticket.

## The four paths

**`trivial`** — one coherent change, one file or a few that clearly belong
together, no new behaviour a user could observe. A typo, a message reworded, a
constant corrected, a missing null check, a test added for code that already
works. Nothing in the file map is load-bearing; the risks are about the change
being pointless, not about it being wrong.

**`small`** — one contained behaviour change with a clear boundary. A new
field on an existing form, one endpoint gaining a parameter, a bug whose fix
is understood and local. The file map is a handful of files in one component.
No public surface changes shape; no data migrates.

**`standard`** — the default, and the one to pick when you are unsure. Real
feature work: several files across more than one component, a public surface
or stored shape that changes, behaviour a user will notice, or anything
touching a boundary the repo treats as load-bearing. Most tickets that were
worth writing a plan for are here.

**`complex`** — the work needs more than one pair of eyes. Several components
coordinated; a migration; a security or authorization boundary; an API other
systems already depend on; concurrency or ordering; a plan whose risks include
something irreversible. Also: a plan you finished reading without being sure
you understood it.

## Rules the judgement obeys

**When two paths both fit, take the more expensive one.** The cost of an
unnecessary lens pass is some tokens and a few minutes. The cost of a missed
regression in a payment path is not comparable, and nothing downstream will
catch what a cheaper path did not look for.

**An epic never reaches here.** `/acs:code`'s gate refuses one, and
`workflow next` exits 2 on one before any classification happens.

**A plan you cannot classify is not a `standard` plan — it is an unfinished
plan.** If `plan.md` has no file map, or a Test strategy that says nothing, you
are being asked to judge an artifact that is not ready. Say so and stop; the
remedy is `/acs:create-impl-plan`, not a guess.

**Size is not stakes, and you no longer have a separate axis for it.** The old
routing had `size` and `stakes` as independent inputs and a grid to combine
them. There is no grid now: a one-file change to an authentication path is
`standard` or `complex` because of *what it touches*, and you say so in the
reason. That the file count is low is not the finding — that the file is
load-bearing is.

## Recording it

One value and one sentence, written together:

```bash
python3 - "<ticket-id>" "<path>" "<reason>" <<'PY'
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

The reason is a sentence about THIS plan, naming what decided it — not a
restatement of the path's definition. "standard: adds a `status` column to
`orders` and two endpoints that read it; the migration is reversible but the
shape is public" is a reason. "standard: it is standard-sized" is not, and it
leaves the Path audit dimension nothing to check against.

`record_delivery_path` refuses an unknown path, refuses an empty reason, and
refuses to move a ticket that is already on a path. That last refusal is the
important one: it is what makes a resumed run read rather than re-judge. When
the plan itself was wrong, the way to move a ticket is
`stop_reason: plan_superseded` — `/acs:ship` re-runs `/acs:create-impl-plan`,
and the corrected plan is classified fresh.
