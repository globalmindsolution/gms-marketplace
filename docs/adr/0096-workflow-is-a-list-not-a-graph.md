# 0096 — The workflow is a list, not a graph: no conditions, no ids, one loop

**Status**: Accepted · **Date**: 2026-09-20

**Supersedes**: [0089](0089-pipeline-order-declared-in-ship-yaml.md)

**Related**: [0008](0008-conditional-steps-as-ticket-data.md) (conditional
steps are ticket data, never invocation options — this ADR extends the same
rule one level out: not workflow data either),
[0092](0092-skill-machinery-declared-per-skill.md)

## Context

ADR-0089 moved the delivery order out of `/acs:ship`'s prose and
`acs_lib/gates.py` into `workflows/ship.yaml`, and that part was right: a
data file two people can read beats an order maintained by hand in two
places. What it also introduced was a small workflow *language* — `needs`,
`when`, `requires`, `paths`, `boundary`, `on_fail`, `on_replan`, `exclusive`,
`max_parallel`, `stop_after`, per-step `id` and `name` — plus
`workflows/phases.yaml` as a registry the schema, the README table and
`/acs:metrics` all derived from.

Three problems followed, and they compound.

**A predicate in the workflow makes a skill untrustworthy standalone.** This
is the load-bearing one. `create-api-contract` ran when `when:
analysis.api_surface == true`. Invoked by hand — `/acs:create-api-contract
MAR-12` — nothing evaluates that predicate, so the skill runs unconditionally
and does work nobody wanted, or refuses on a rule it cannot see. The
condition was *about the change*, and the file asserting it never read the
change. A skill whose applicability lives outside it has two behaviours, and
only one of them is tested.

**`skipped` is a decision the workflow has no standing to make.** A step
skipped by a false `when` recorded `status: skipped` and satisfied every
`needs` edge pointing at it. So the ledger said a contract step was
"handled", and the evidence for that claim was a predicate in a YAML file,
not a sentence from the skill that owns the question.

**The registry was a fifth central list of the skills.** `phases.yaml` had to
agree with the skill directories, the agent files, the two closed enums in
the state schemas, and the `argparse` choices in `acs start` / `acs finish`.
Five lists, one fact. Every new skill was five edits, and the failure mode of
missing one was silent.

The DAG bought nothing for this, either. `ship.yaml`'s steps were a straight
line with `needs` edges naming the previous step, which is a list written
twice.

## Decision

**`workflows/ship.yaml` is version 3: a `version`, a flat list of skill
names, and one optional `loops:` entry.** The schema REJECTS `when`, `paths`,
`requires`, `needs`, `max_parallel`, `exclusive`, `on_fail`, `boundary`,
`delivery`, `id`, `name` and `stop_after`. The declared order IS the
dependency order and **every step runs on every run**.

**A step that owes nothing records an evidenced no-op.** Its own pre-hook
reads the plan's `## Contract` block (ADR-0098) and completes the step from
it, at no token cost, carrying the sentence that says why. Silence is not
permission to skip: a step with no Contract entry to stand on runs and
decides for itself, then records the reason. The saving is the same one the
predicates bought; the difference is who is accountable for the claim.

**`loops:` is the only construct, and it is not a condition.** It tests
nothing about the change — it declares that two steps form a cycle and how
many times: `from: review-code`, `back_to: code`, `max_iterations: 3`,
`on_exhausted: fail`. It cannot live inside a skill because it spans two of
them, which is exactly the test for what belongs in a workflow file.

**Order is validated, not declared twice.** Each skill ships
`skills/<name>/acs.yaml` — `phase`, `reads.required`, `reads.optional`,
`writes` — and `acs.py workflow validate` checks that every step's required
reads are written by an earlier step. Swap two steps whose order does not
matter and it passes; swap two whose order does and it names the pair and the
line.

**`workflows/phases.yaml`, `schemas/phases.schema.json` and the kernel's
`phases` module are removed**, along with the "only build/test/ship
skills may be steps" rule and the closed skill enums in the state schemas and
the CLI. A skill is a directory; an agent is a naming convention; a step name
is validated against the resolved workflow.

What ADR-0089 decided and this ADR keeps: the order lives in a data file, a
consumer replaces it **wholesale** with `<repo>/.acs/workflows/ship.yaml`
(override, never a merge), the parser is the stdlib-only
`acs_lib/yamlsubset.py`, `_require_completed` stays deleted, and each
pre-hook checks only the inputs that skill reads plus a small set of safety
brakes.

## Consequences

**Every skill is invocable standalone and behaves the same way when it is.**
This is the property the whole redesign rests on. A skill reached through
`/acs:ship` and a skill typed by a person evaluate the same conditions,
because the conditions are inside the skill.

**A no-op is auditable where a skip was not.** `steps/create-api-contract/`
holds a completed step with a recorded reason, rather than an absence the
ledger calls "handled".

**The consumer's workflow file is now writable by hand.** Ten lines, no
language to learn. That is what makes "add more workflows" safe: a consumer
owns the pipeline, the plugin owns the skills, and a consumer cannot change
what a skill reads, writes or is a leg of, because those facts ship inside
the plugin beside the skill.

**What this gives up, stated plainly:** a workflow can no longer express
"run these two in parallel" or "stop here". Parallelism inside a step stays
the skill's business (`/acs:create-docs` still fans its sets out); a step
that should not run in a given repo is a step left out of that repo's list.
Neither has come up as a real need that a skill could not answer for itself,
and buying them back costs the standalone property above.

**A repo that overrode `.acs/workflows/ship.yaml` must port its override.**
There is no adapter: a v1 or v2 file is refused with the offending line
named. The shipped `workflows/ship.yaml` is the worked example.
