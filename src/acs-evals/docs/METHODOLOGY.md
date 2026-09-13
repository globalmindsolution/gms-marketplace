# Methodology and limitations

A datasheet for this dataset: what it is, how it was built, what it can and
cannot tell you, and where it is weakest. Read this before quoting a green run
as evidence of anything.

## Intended use

**In scope.** Deciding whether a given `acs` plugin build behaves the way the
last recorded build behaved, across the surfaces listed in the README — as a
release gate, and as a regression net during development.

**Out of scope, and not merely unmeasured:**

- **Whether acs's behaviour is *correct*.** Every expectation records what the
  plugin *did*, not what it *should* do. A case passing means "unchanged", never
  "right". Where a behaviour is known to contradict its own contract, it is
  pinned as a `known_divergence` and reported, precisely because the dataset
  cannot make that judgement itself.
- **Whether acs is useful, or produces good code.** Nothing in *this* tier
  evaluates output quality. Tier 3 measures a proxy for it — verify iterations
  to pass, achieved coverage, unresolved blocking findings — see
  [`PERFORMANCE.md`](PERFORMANCE.md).
- **Runtime skill routing.** Unverified *here*; tier 3 measures it against a
  declared decision rule. See *Threats to validity* below.
- **Performance, cost, or token consumption.** Out of scope for the
  deterministic tier by construction — it runs no model. These are tier 3's
  subject: [`PERFORMANCE.md`](PERFORMANCE.md).

## How expectations were produced

Every expectation was **observed, not derived from reading source**. The build
was driven in a sandbox, the real output captured, redacted, and pinned. Where
a value was predicted from a contract first, it was then confirmed against a
real run before being committed.

Two groups are **generated** rather than authored:

| Group | Generated from | Regenerate with |
|---|---|---|
| `11-schema-constraints` | the shipped JSON schemas | `make generate` |
| `evals/routing` | `dataset/routing.json` | `make generate` |

`make check` fails if either drifts from its source, so a hand edit to a
generated file cannot survive unnoticed.

## Sampling and coverage

The dataset is **not** a random sample; it is a targeted selection:

1. Everything the v0.4.10 changelog changed (MAR-520 – MAR-530).
2. The pipeline spine every release depends on regardless of the changelog.
3. The packaged surfaces a source-tree test suite cannot see — skills, schemas.

Coverage of the schema tier is **measured, not asserted** — every constraint is
deleted in turn and the suite re-run:

```bash
make mutation                                # the current number
python3 runner/mutation_sweep.py --holes     # every constraint nothing pins
```

The CLI tier's equivalent is `runner/mutation_cli.py` (`make mutation-cli`).
It copies the build, mutates one decision site in one `acs_lib` module — a
comparison negated or moved by one, `and`/`or` swapped, a boolean flipped, a
`not` dropped, an `if` test negated, an integer nudged — runs the CLI cases
against the copy through `ACS_PLUGIN_ROOT`, and counts the mutant killed if any
case fails. It runs the unmutated copy first as a control and refuses to report
a number when that fails. The number is a **kill rate over a seeded sample**
(705 sites across eight modules at 0.4.9; ~15 s per mutant, so the default
sample is 40). First measurement, 2026-09-10: **14/40 killed (35%)** on the
40-mutant sample, `derive.py` and `gates.py` at zero — quote it with its sample
size, and read the survivors it lists. Reading them is what the number is for:
the first sweep's survivors in the file-map guard and the lock's same-host
regime became `12-filemap-guard` (15 cases) and `LOCK-008`–`011`, recorded
from the build the way every case is, and `mutation_cli.py --site` then showed
the mutants at those sites killed (12 of 13; the one left is equivalent for
every input a record can carry) —
a survivor is a hole or an equivalent mutant, and the tool cannot tell which.
This replaces the hand-run spot check of seven decision-table mutations (six
caught) that used to stand in for a measurement here.

## Threats to validity

Listed worst-first. Each is a real reason a green run could mislead you.

### 1. Generated schema cases are derived from the schemas they test

`11-schema-constraints.json` reads a schema, breaks one of its constraints, and
asserts the schema rejects the result. This is circular by construction: it can
detect a schema **changing**, but it can never detect a schema being **wrong**.
A schema that has always required the wrong field will be pinned, faithfully,
forever.

The hand-written cases in `08-schemas.json` are the counterweight — they encode
a human's view of what a constraint is *for* — but they are the minority.
Treat the generated tier as change-detection, not validation.

### 2. Routing is unverified at runtime

`evals/` has never been executed. `claude plugin eval` is early access and was
not enabled on the account this dataset was built with, so its case and grader
schema is authored from the CLI's `--help` output rather than a passing run.

What *is* verified without a model is the routing **surface**: that all 25
skills ship, carry a description, and declare the right
`disable-model-invocation` (`SKILL-*`). **Whether a real request reaches the
right skill is not pinned by the deterministic tier.** Do not record routing as
verified on the strength of a tier-1 gate.

Tier 3 measures it without waiting for early access: `runner/measure_skills.py`
drives the same `dataset/routing.json` prompts through plain `claude -p` with
only the `Skill` tool allowed, killing the session at the first `Skill` call.
The two explicit probes (`/acs:install-hooks`, `/acs:update`) cannot be seen
that way — a typed slash command is expanded by the CLI and never dispatched
through the `Skill` tool — so they are decided at the `init` event's
`slash_commands` list and killed there, before any model turn; each run records
its `detection` rule so the two kinds are never read as one. Three **control**
probes with known answers (a registration canary, an unregistered command, an
off-domain request) check the instrument itself, and the free ones run as a
pre-flight that refuses to spend when the sandbox cannot see the plugin — the
failure mode that produced 22 phantom misses per paid run before it was found.
Its decision rule is stated in [`PERFORMANCE.md`](PERFORMANCE.md) — a positive
probe passes only if it routes on **all** runs, a split result is a finding, and
a negative probe that auto-invokes even once is `critical`. That answers the
"`runs: 3` with no declared rule is not a criterion" objection this section
raised. **First run 2026-09-10** (`dataset/baselines/acs-0.4.9-routing.json`):
27 of 30 probes unanimous over 5 runs, one probe's prompt found to carry no
request and corrected (scenario set 1.3.0), two skills split 4/5. Those two
were first triaged as description defects; diagnostic sessions showed the
model naming the right skill every time and, on the miss runs, inspecting the
empty seeded repo first, finding no codebase to reverse-engineer and no
finished change to sync, and asking instead of routing. The sandbox had made
the prompt false. Scenario set 1.5.0 lets a probe name the sandbox its prompt
presupposes (`profile`, deterministic `setup` steps), and both re-measured
5/5 with their prompts unchanged — 30 of 30 unanimous. The lesson is the
methodological one: a routing probe tests a description only when its
presupposition holds, so a split is triaged against the sandbox before the
description. Before that run routing was unmeasured in fact, and the sentence
that follows is kept because the point still stands — but
it is no longer unmeasurable.

### 3. The baseline is a moving target

`recorded_against` in `dataset/manifest.json` names the build the goldens came
from. Run against a different build, "no regression" only means "no *unexpected*
change" — the report says so, but a reader skimming for green can miss it.

### 4. Single-observation goldens

Each deterministic case is recorded from **one** run. That is sound because the
tier is deterministic by construction (fixed sandbox, redacted clocks and
paths), but any surface that turned out to be non-deterministic would be pinned
to whichever value was observed first. The one place this bit us — a generator
expanding a clock token at build time — was caught by `make check`, not by the
suite.

### 5. Severity is a judgement

The levels in [`RUBRIC.md`](RUBRIC.md) were assigned by the dataset's author
against stated criteria, not derived from incident data. They are reviewable and
should be argued with; a case in the wrong band is a defect in the gate.

### 6. Tier 3's thresholds are uncalibrated, and its corpus is three scenarios

No tier-3 measurement has been taken, so `dataset/thresholds.json` carries
`basis: provisional` and its relative gates cannot block a release — they report
only. The pipeline corpus is three scenarios, so cost and quality findings
generalise no further than the surfaces those three touch, and a sandbox run is
not a consumer run. [`PERFORMANCE.md`](PERFORMANCE.md) lists these worst-first.

### 7. The harness and the dataset share an author

The same person wrote the cases and the runner that judges them, so a blind spot
in one is likely mirrored in the other. `mutation_sweep.py` exists to reduce
this — it asks whether the suite catches anything, independently of whether it
passes — but it covers only the schema tier.

## Independence

The dataset lives in a separate repository from the plugin deliberately: it
cannot be edited in the same change that alters the behaviour it pins, so
weakening a case and changing the code are two reviewable acts, not one.

The counterweight to that independence is drift — a plugin change that adds a
surface leaves this repo behind. The release checklist's "new surfaces have
cases" step is the only thing closing that loop, and it is a human step.

## Reproducibility

- Stdlib only, Python ≥ 3.9. No network, no model, no external services.
- One fresh sandbox per case: no case can see another's writes.
- Run-specific values (paths, checkout ids, timestamps, the build root) are
  redacted to stable tokens before matching.
- Time-relative fixtures use `{{now}}` / `{{hours_ago:N}}` so a lock's meaning
  stays fixed as the clock moves.
- Generation is deterministic and `make check`-verified.

A run is fully described by `results/latest.json`: the build, the dataset
version, the baseline, every case's status and severity, and the diffs.
