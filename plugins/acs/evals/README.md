# acs plugin evals

`claude plugin eval` cases for the acs plugin, laid out the way the
[reference](https://code.claude.com/docs/en/plugin-evals) specifies: one
directory per case, grouped under the non-case directory `routing/`.

```
plugins/acs/evals/
└── routing/<case>/
    ├── prompt.md            # frontmatter: max_turns, allowed_tools; body: the prompt
    └── graders/<name>.md    # one grader per file
```

## This tree is generated. Do not edit it by hand.

The prompts and the skill each one must (or must not) route to are curated in
`evals/dataset/routing.json` at the repo root, and rendered from there by
`evals/runner/gen_plugin_eval.py`. A hand edit is lost on the next render, and
`make -C evals check` fails on a stale or orphaned file. Change the JSON.

```bash
make -C evals generate      # re-render
make -C evals check         # fail if stale (runs in the gate)
```

## Running it

```bash
make -C evals routing-cases                              # ~$0.12/run, 40 cases x 3 runs
make -C evals routing-cases ROUTING_RUNS=1               # smoke test, not a rate
make -C evals routing-cases ROUTING_ABLATION=with-without # buy the no-plugin baseline arm
```

`ROUTING_MAX_USD` is the cost ceiling — the reference is explicit that this,
rather than a tight `max_turns`, is the lever for cost. Results land in
`evals/results/` at the repo root and in this directory's gitignored
`results/`.

## What these cases assert, and what they do not

Each probe renders exactly one grader, so a case score **is** the routing
verdict: 1.00 routed as asserted, 0.00 did not. Nothing here grades whether a
skill's own work was any good.

The grader is the reference's canonical routing check — `tool_used` on the
`Skill` tool with an `input_match` regex naming the skill:

```yaml
type: tool_used
tool: Skill
input_match: '"skill"\s*:\s*"(?:[\w-]+:)?code"'
min: 1
```

It reads the tool call rather than the final message, which is why a skill
whose precondition gate refuses for want of an `.acs/` workspace still counts
as a route — the call happens before any gate runs. No scaffold, no seeded
sandbox, no `--scaffold`.

Negative probes are the same grader with `min: 0`, `max: 0` and `arm: both`.
Both bounds are deliberate: `min` defaults to 1, so a lone `max: 0` asserts the
impossible range `1..0`.

## Why this is not in CI

ADR-0022: behavioural and LLM evals never run in CI. These cases spawn real
sessions and cost money, so they stay out, and the invariant is enforced by a
grep that must keep returning nothing:

```bash
grep -rn "run_evals\|evals/behavioural/\|plugin eval" .github/workflows/
```

The reference's CI guidance is written for suites without that constraint. What
*does* gate every PR is `make -C evals check`, which is free: it proves this
tree still matches the dataset it is rendered from.

## Related

- `evals/` at the repo root — the dataset, the renderer, and tiers 1 and 3.
- `CLAUDE.md` — "Three grading layers, deliberately separate".
