# The acs evaluation process

How this suite is used to decide whether an `acs` plugin build is fit to
release. It is written to be followed by someone who did not build the dataset.

- **What it answers:** has the plugin's observable behaviour moved since the
  last release?
- **What it does not answer:** is the plugin *good*? Whether a behaviour is
  correct is a human judgement; this process only makes every change to it
  visible and deliberate.

## Roles

| Role | Owns |
|---|---|
| **Release engineer** | Runs the gate before a version bump. Decides go / no-go. |
| **Reviewer** | Reads the report on the release PR. Signs off on divergences. |
| **Dataset maintainer** | Adds cases for new surfaces; re-records goldens when a change is intended. |

On a small team one person wears all three hats. The point of separating them
is that **the person who re-records a golden should not be the only person who
sees the diff.**

## The gate

One command, run from `src/acs-evals/` in a clean checkout.

```bash
export ACS_PLUGIN_ROOT=$PWD/../../plugins/acs   # the build being released
make gate
```

`make gate` runs four steps and stops at the first failure:

1. **`make eval`** — the deterministic tier. 455 cases against the resolved
   build, writing `results/latest.json`. Non-zero exit if any case differs.
2. **`make check`** — asserts both GENERATED trees are still in sync with their
   sources: `evals/**/case.yaml` against `dataset/routing.json`, and
   `dataset/cases/11-schema-constraints.json` against the shipped schemas.
   Catches a generated file edited by hand, where the edit would be silently
   overwritten.
3. **`make mutation`** — measures what the schema tier would actually catch, by
   deleting each constraint in turn. Fails below 90% coverage.
4. **`make report`** — renders `results/report.md` and `results/report.html`
   from the run result.

Attach `results/report.md` to the release PR.

### What "the build under test" means

`ACS_PLUGIN_ROOT` unset is the **default and the more honest check**: the runner
resolves the newest *installed* build under
`~/.claude/plugins/cache/*/acs/*/`, which is what a consumer actually executes.
Setting `ACS_PLUGIN_ROOT` points it at a working tree instead — right for
pre-release verification, wrong for confirming a published release.

Run it **both ways** before a release: the working tree tells you the code is
right, the installed build tells you the packaging is.

## When to run it

| Trigger | Tier | Who |
|---|---|---|
| Before any version bump | full gate, both build sources | Release engineer |
| On a PR that touches `plugins/acs/` | `make eval` | Author |
| After publishing a release | full gate against the *installed* build | Release engineer |
| When adding a plugin surface | `make eval` + new cases | Dataset maintainer |

This suite deliberately runs in **no CI workflow**. The deterministic tier
needs an `acs` build resolved on the machine, and the plugin's own policy (C-4)
keeps eval execution local rather than in CI. Running it is a step in the
release checklist, not a background job — see
[`RELEASE-CHECKLIST.md`](RELEASE-CHECKLIST.md).

## Triaging a failure

**First read the severity.** [`RUBRIC.md`](RUBRIC.md) decides whether the run
blocks: a `critical` failure stops the release with no exceptions, a `major` one
blocks unless the golden is deliberately re-recorded, and `minor` drift does not
block but must still be triaged before the next cut. The runner prints the
verdict and exits accordingly.

A red case is **a behaviour change**, not automatically a defect. There are
exactly three outcomes, and the process is choosing between them.

```
   red case
      │
      ├── the build behaves differently and that is WRONG
      │       → regression. Fix the plugin. Do not touch the golden.
      │
      ├── the build behaves differently and that is INTENDED
      │       → re-record this case, in its own commit, with the ticket that
      │         changed it named in the message. A reviewer reads the diff.
      │
      └── the build is right and the CASE was wrong
              → fix the case. This is a dataset bug; say so in the message.
```

Work it like this:

```bash
# 1. see exactly what differs
python3 runner/run_golden.py -v --case VERDICT-009

# 2. read the case — its `title` and `note` say what it was pinning and why
grep -A30 '"id": "VERDICT-009"' dataset/cases/03-verdict.json

# 3. reproduce by hand against the build, in a scratch repo
python3 $ACS_PLUGIN_ROOT/hooks/scripts/acs.py verdict show --ticket TKT-1 ...
```

Only once you can say **which of the three outcomes it is** do you change
anything.

### Re-recording

```bash
make record              # rewrites expectations from the current build
git diff dataset/cases/  # READ EVERY LINE
```

Re-recording is kind-aware: a schema case comes back with `valid` plus the
constraint its rejection named, a skill-manifest case with its frontmatter
assertions, and a case authored against `stdout_json_subset` keeps a subset
over the same keys rather than widening to an exact match. It does **not**
rewrite generated cases — regenerate those with `make generate`.

Rules, because this is the one operation that can quietly destroy the gate:

- Re-record **only the cases you have decided about** — `make record` rewrites
  everything selected, so narrow it: `python3 runner/run_golden.py --record
  --case 'VERDICT-*'`.
- Commit the re-recording **separately** from any other change, with the
  ticket that justifies it in the message.
- Never re-record to turn a red run green without reading the diff. That
  converts the gate into a rubber stamp, and it will not catch the next
  regression either.
- After re-recording, run `make mutation`. A drop in coverage means the
  re-recording weakened what the suite pins, whatever the case count says.

## Known divergences

A case may pin behaviour that **differs from what the code's own contract
states**. These are recorded deliberately: the case asserts what the build
actually does, and carries a `known_divergence` block saying what the contract
says instead, what causes the gap, how far it reaches, and what to change if
it is closed.

They surface in the report under **Known divergences**, and each needs a
decision before release: *fix it now*, or *accept it for this release and say
so in the changelog*.

When a divergence is closed in the plugin, its case fails — which is the point.
Flip the expectation and delete the `known_divergence` block in the same commit
as the fix lands.

## Extending the dataset

Add a case when a plugin change introduces an observable surface, or when a bug
escapes to a consumer.

1. Drive the surface by hand first and capture what it really does. **Never
   write an expectation from reading the source** — the dataset's value is that
   it records observed behaviour.
2. Add the case to the right `dataset/cases/NN-*.json` group, with a `title`
   that states the property, not the mechanics. "high stakes lifts even a
   trivial change to STANDARD" beats "test lane derive with high stakes".
3. Add a `note` whenever the *why* is not obvious from the title.
4. Tag it with `covers` so it shows up in the report's ticket rollup, and give
   it a `severity` if the group default is wrong for it — apply the test in
   [`RUBRIC.md`](RUBRIC.md#test), and let ties go to the higher level.
5. Run it. Then deliberately break the expectation and run it again, to prove
   the case can actually fail. A case that cannot fail is worse than no case.

For a routing probe, edit `dataset/routing.json` and run `make generate`.

## The other two tiers, and what this process does not cover

### Tier 3 — skill quality, reliability, cost and time

The process above gates **contracts**. It cannot tell you whether skills got
less reliable, worse, more expensive or slower, because it runs no model. Tier 3
does, and it is part of `make gate`:

```bash
make measure-plan   # what it will run and what it will cost — free
make measure        # SPENDS MONEY; needs `claude` on PATH
make perf           # judge it; pure, offline, re-runnable
```

`make perf` reports **UNMEASURED** and fails until a measurement exists. That is
the design: absence is not a pass. Full rules, verdicts and limitations in
[`PERFORMANCE.md`](PERFORMANCE.md).

Triage differs from tier 1 in one way. An **absolute** failure — a routing
probe that split, a run that did not complete, a run that ended carrying a
blocking finding — is triaged exactly like a `major` or `critical` case here.
A **relative** one — cost, time, iterations, coverage against a baseline — is
currently a prompt to look rather than a defect, because the thresholds are not
yet calibrated. Do not re-baseline a regression away to clear it; that is the
tier-3 equivalent of re-recording a golden to hide a bug.

### Tier 2 — `claude plugin eval` routing

`evals/` holds `claude plugin eval` cases for skill routing. **They have never
been executed** — the feature is early access and was not enabled on the
account this dataset was built with, so the grader schema is authored from the
CLI's `--help` output rather than a passing run.

This is no longer the gap it was. Tier 3 measures routing from the same
`dataset/routing.json` prompts through plain `claude -p`, against a stated
decision rule, with no early access needed. Tier 2 remains worth validating for
its ablation support (`--ablation with-without`), which tier 3 does not do:

```bash
claude plugin eval acs --case route-code --runs 1   # confirm the schema
claude plugin eval acs --tag routing                # then the full tier
```

Fix any schema mismatch in `runner/gen_plugin_eval.py` and regenerate.

### Still not covered by any tier

How acs behaves on **real tickets**. Tier 3's pipeline scenarios run in a
throwaway sandbox on a trivial change, so its cost and quality numbers are
release-over-release deltas, not an estimate of what a consumer's ticket costs.
Treat that as an open gap.
