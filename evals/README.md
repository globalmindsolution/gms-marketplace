# acs evals

The suite that grades the acs plugin is `claude plugin eval` cases, living
inside the plugin at [`../plugins/acs/evals/`](../plugins/acs/evals/) and laid
out the way <https://code.claude.com/docs/en/plugin-evals> specifies. This
directory holds the curated dataset those cases are rendered from, the
renderer, and the commands that drive them.

```
evals/
├── dataset/routing.json        # the curated probes: prompt -> skill it must (not) route to
├── runner/gen_plugin_eval.py   # renders them into ../plugins/acs/evals/routing/
├── behavioural/                # real-session scenarios, not yet migrated (see below)
└── Makefile                    # every command
```

```bash
make -C evals help            # every target
make -C evals check           # free: fail if the case tree is stale against the dataset
make -C evals generate        # re-render the case tree
make -C evals routing-cases   # PAID: run the suite (~$0.12/run; 40 cases x 3 runs ~ $15)
```

## What this replaced, and why

Until the migration this directory held three home-grown tiers: a 355-case
deterministic golden suite with its own runner, schema-constraint generator and
mutation sweeps; a tier-3 session measurer with a performance gate; and the
behavioural scenarios. Routing alone was measured **three** separate times — by
the tier-3 measurer, by `behavioural/.../s04_skill_triggers.py` off its own
hard-coded list, and (latterly) by the guide-format tree.

`claude plugin eval` expresses the model-driven part of that directly, so the
bespoke machinery went. Git history has all of it.

Two consequences worth stating plainly rather than discovering later:

- **The deterministic tier ran no model.** It asserted a shipped build's
  observable surface — exit codes, JSON, refusal messages, schemas, skill
  frontmatter. That is a contract suite, not an eval, and the guide's format
  cannot express it without spending an agent session per case. It was removed
  on request; `tests/` is where that kind of assertion belongs.
- **Explicit-invocation probes are no longer measurable.** A typed
  `/acs:<skill>` is decided by the session's registration list *before any model
  turn*, so no grader in the guide can see it — `tool_used: Skill` reports zero
  calls. The old `s04` harness measured it from the registration list. Nine such
  probes exist; seven read as failures for this reason alone.

## The dataset is the source of truth

`dataset/routing.json` is curated and reviewed here; the case tree under
`plugins/acs/evals/routing/` is rendered from it and a hand edit there is lost
on the next render. `make -C evals check` fails on a stale or orphaned file and
runs free in CI.

Each probe carries a `why`, which is rendered into the grader body so the case
explains itself to whoever reads a failure.

## Behavioural scenarios: still bespoke

`behavioural/` holds eight real-session scenarios in a custom Python harness.
The free tier is deterministic, costs nothing, and runs on every commit via the
`acs-free-evals` pre-commit hook; the paid tier spends money and runs on demand.
They are the next thing to migrate to the guide's format — they assert artifacts
and hook behaviour, which `file_exists`, `regex` over a file's contents and
`tool_used` graders can express, with `case.yaml`'s `context.scaffold_script`
seeding the workspace.

## Not in CI

ADR-0022: behavioural and LLM evals never run in CI. These cases spawn real
sessions and cost money. The invariant is a grep that must keep returning
nothing:

```bash
grep -rn "run_evals\|evals/behavioural/\|plugin eval" .github/workflows/
```

What gates every PR is `make -C evals check`, which is free.
