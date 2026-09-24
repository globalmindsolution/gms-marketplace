# acs eval suite

`claude plugin eval` cases for the acs plugin, in the layout
<https://code.claude.com/docs/en/plugin-evals> specifies. The case files **are**
the suite: there is no dataset they are rendered from and no generator to run.
Edit a case by editing its files.

```
evals/
├── routing/                  # 258 cases: does a prompt reach the right skill?
│   └── <case>/
│       ├── prompt.md         # frontmatter: description, expected_outcome, tags, limits; body: the prompt
│       └── graders/<name>.md # one grader per file
├── artifacts/                # 2 cases: did the skill WRITE the right workspace state?
│   └── <case>/               # + case.yaml (scaffold) + a seed script
├── setup/                    # 8 cases: does /acs:setup configure exactly what was asked?
│   ├── _fixtures/            # the repo every case starts from (not a case)
│   └── <case>/               # prompt.md + case.yaml (scaffold.sh) + graders/
└── results/                  # written by each run; gitignored
```

## Running it

From the plugin root (`plugins/acs/`), or with `plugins/acs` as the target from
the repo root:

```bash
claude plugin eval . --tag routing --ablation none              # every routing case, 3 runs each
claude plugin eval . --tag routing --ablation none --runs 1     # smoke test, not a rate
claude plugin eval . --tag confusable --ablation none           # only the prompts that borrow a neighbour's words
claude plugin eval . --case route-code --runs 1 --ablation none # one case, while iterating
claude plugin eval acs@gms-marketplace --tag routing --ablation none   # the INSTALLED build
claude plugin eval . --tag artifacts --scaffold --allow-tools Write Edit Bash   # see artifacts/README.md
claude plugin eval . --tag setup --scaffold --allow-tools Bash Write Edit --judge-model sonnet   # see below
```

Pin `--model` before recording a number you mean to compare with a later run:
unpinned, a model rollout is indistinguishable from a plugin regression.
`--max-cost-usd` is the cost lever. A routing run is one model turn (see below)
and costs about $0.075 (measured over 208 one-turn runs on 2026-09-24), so the
release gate's ~2,500 runs cost about $190.

## Tags

| Tag | Cases | Asserts |
|---|---|---|
| `routing` | all 258 routing cases | a prompt reaches (or avoids) a skill |
| `description` | 240 | a natural-language request, never naming the skill, reaches it — ten phrasings for each of 24 skills |
| `confusable` | 72 | (a subset of `description`) the phrasing borrows a neighbouring skill's vocabulary |
| `explicit` | 8 | a typed `/acs:<skill>` reaches it — see the limit below |
| `negative` | 6 | a description of an internal leg's subject does NOT reach the leg |
| `control` | 4 | a request answered in prose invokes no skill at all |
| `artifacts` | 2 | the skill wrote the expected workspace state |
| `setup` | 8 | /acs:setup writes what was asked and nothing else; 2 of them assert it does not fire |

`--tag` keeps a case if ANY of its tags match, so `--tag description --tag
negative --tag control` runs the routing cases that are fully measurable —
which is exactly what the release gate runs.

Each of the 24 skills a user reaches by describing the work has ten
phrasings: plain requests, indirect ones with the context stated in the
prompt, and `confusable` ones that borrow a neighbour's words — "don't merge
anything, just open the pull request", "not a design for one ticket: regenerate
the product-wide C4 views". Each confusable case's `description` names the
neighbour. One prompt per skill measured one sentence; ten, run ten times each,
measure the description on 100 runs
([ADR-0109](../../../docs/adr/0109-routing-gate-ten-phrasings-ten-runs.md)).

## How routing is graded

Every routing case carries exactly one free, deterministic grader, so a run
scores 1.00 (routed as asserted) or 0.00 (did not), and a case's score is the
fraction of its runs that routed. It is the reference's canonical routing
grader — `tool_used` on the `Skill` tool, with an `input_match` regex naming the
skill:

```yaml
type: tool_used
tool: Skill
input_match: '"skill"\s*:\s*"(?:[\w-]+:)?code"'
min: 1
```

`input_match` narrows the count to calls naming that skill, bare or
plugin-qualified, and the closing quote keeps `code` from matching `code-small`.
It reads the tool call rather than the reply, so a skill whose precondition gate
refuses AFTER it routed still counts as a route — which is what routing means.

A negative is the same grader with `min: 0`, `max: 0` and `arm: both`. Both
bounds are deliberate: `min` defaults to 1, so a lone `max: 0` asserts the
impossible range `1..0`.

**A routing run is one turn** (`max_turns: 1`), so only the model's first move
is graded. The grader counts Skill calls across the whole run, and skills call
skills: `/acs:ship` invokes each step with the Skill tool, and `/acs:code`
dispatches its leg the same way. With ten turns, a request wrongly routed to
`ship` passed a step's case as soon as `ship` reached that step, and a request
correctly routed to `code` failed a leg's negative as soon as `code` dispatched
the leg. The CLI passes `max_turns` to the child as `--max-turns` and grades
the tool calls in the trace whatever the exit status, so a run that stops at
the limit is still scored.

## Why `--ablation none`

It halves the spend, and for routing the baseline arm answers nothing: baseline
Claude has no acs skills, so it structurally never routes to one. It is a cost
choice, not a correctness one — `tool_used: Skill` graders are excluded from a
two-arm score, but only when a case has other graders to score, and every
routing case here has exactly one.

## What the release gate passes

`release.pre_release_gate` in `.acs/settings.json` runs three commands, and the
first non-zero exit stops the cut ([ADR-0107](../../../docs/adr/0107-routing-gated-by-skill-not-by-prompt.md)):

1. `python3 -m unittest discover -s tests/evals -p check_*.py` — free: a
   malformed case, or a grader that cannot fail, stops the cut before anything
   is spent.
2. `claude plugin eval plugins/acs --tag description --tag negative --tag
   control --ablation none --runs 10 -j 8 --threshold 0 --json …` — the paid
   run, ten runs a case. `--threshold
   0` stops the CLI from judging; the result goes to a file.
3. `python3 scripts/eval_gate.py <that file> --min-skill-rate 9/10
   --min-suite-rate 1` — the judgement.

The CLI judges one case at a time: it exits 1 if any case scores below
`--threshold`, which defaults to 1.0. For routing that is the wrong unit. The
model is stochastic, so a skill that routes right 90% of the time scores 3/3
on a prompt only 73% of the time, and across the 240 description cases the
chance that every one scores 3/3 is effectively nil. A gate at 1.0 fails on
almost every run whether or not anything is wrong. The old gate was also
unpassable for a second reason: it ran the `explicit` cases, six of which
scored 0.00 in the first full run for a reason no grader can see.

`scripts/eval_gate.py` applies this policy instead:

| Kind | Rule | Why |
|---|---|---|
| `negative`, `control` | every run must pass | pulling a request onto an internal leg, or firing a skill on a git question, is a defect however rarely it happens |
| `description` | each **skill**, pooling its ten phrasings (100 runs), routes at least **9/10**; the **suite** routes **every run** | the floor names a weak skill; the suite rate of 1.0 is the binding rule — one misroute anywhere fails the release (ADR-0109) |
| `explicit` | not gated | not observable — see the limit below |

It fails closed on anything it cannot read: a partial run (cost ceiling hit), an
unknown result format, a case it cannot map to a skill, a gated case missing
from the run, or a result older than six hours. The CLI only warns when it
cannot write `--json`, so without that last check a stale file from an earlier
run could be judged in place of this one.

**The rates were set by the owner, not by a baseline** (ADR-0109). A suite
rate of 1.0 means every one of about 2,400 description runs must route, so the
gate fails until every weak description is fixed. The partial run of 2026-09-24
had `review-code` at 0/9 and `docs-sync` at 1/9. More phrasings measure a
description more precisely; they do not improve it.

## How the graders are shown to be right

A grader is trusted only after it has passed four checks. Two are free and run
locally — never in CI (see [Not in CI](#not-in-ci)). Two are paid and **have not
been done yet**.

| Check | What it proves | Where | Status |
|---|---|---|---|
| Well-formed | every case and grader uses keys and values the CLI accepts; every routing regex matches its own skill, bare and qualified, and no other shipped skill | `tests/evals/check_cases.py` | free, local |
| Calibrated | every free grader in `setup/` and `artifacts/` passes an ideal run and at least one fails each bad run, built from the case's real scaffold and the plugin's real writers and graded the way the CLI grades | `tests/evals/check_grader_calibration.py` | free, local |
| Can fail | each case scores lower against a deliberately broken plugin — a skill removed, a description blanked, a known bug put back | a paid run | **not done** |
| Judge agrees | each `llm` grader's verdict matches a human's on hand-labelled transcripts | a paid run with `--judge-model sonnet` | **not done** |

The calibration test found two graders that could not fail. They have been
fixed. It also mirrors the CLI's grading rules, which were read out of the CLI
itself (claude 2.1.281):
- A regex grader whose file does not exist **fails** in every match mode,
  `not_contains` included.
- `file_exists` and the `files` target see only the paths **created** during the
  run.

- **`create-ticket-artifacts`** passed a run that started the skill and wrote
  nothing. The allocate step, the skill's mandatory first action, writes a
  placeholder ticket that already has the right id, type and `needs_design`.
  Two graders now require real content: at least one acceptance criterion, and
  a title that is no longer the placeholder.
- **`resume-and-verify`** passed on `/health` appearing anywhere in `app.py`,
  including a comment. It now requires the quoted route string.

Phase 2, on a host where Bash works inside eval runs:
1. Pilot every new case once.
2. Run against a broken plugin to confirm each case can fail.
3. Calibrate the judges.
4. Take the ten-run baseline the gate is judged against.

## How the setup cases are graded

The `setup/` cases follow the reference's authoring rules rather than the
routing conventions: each is scored in both arms (with and without the plugin,
so `Δ` is the plugin's contribution), runs three times, and carries at least
one grader on what the run PRODUCED. The `tool_used: Skill` grader is there for
display only. Every case starts from `_fixtures/python-repo.sh` — a small
pytest project on `main` with a fixed remote — and `04-rerun` adds a setup run
from before, made by the plugin's own wizard.

| Case | Asks | Graded on |
|---|---|---|
| `01-keep-defaults` | keep the formats, no CI | no settings file, no CI files, the ignore entry written, no stray answers file, no re-asked question |
| `02-custom-pr-title` | a bracketed-id PR title + the convention check, not an admin | only `pr_title` written, the convention workflow and checker installed, no other gate, no branch-protection PUT, the reply names the required check |
| `03-tests-gate` | the tests-and-coverage gate | a pytest `tests.command` that enforces `$ACS_COVERAGE`, `acs-tests.yml` installed, nothing else |
| `04-rerun` | run it again, change nothing | the custom format kept, no duplicate ignore line, no new gate, the reply reports nothing changed |
| `05-no-choices` | "Set up acs for this repo." | nothing written; the reply asks about formats and CI |
| `06-invalid-branch-format` | a branch format without `{ticket_id}` | no settings file left behind; the reply explains why and offers a working format |
| `07-neg-github-actions`, `08-neg-pre-commit` | CI or tooling work that is not about acs | setup never fires, no acs file is created, the request itself is done |

Every `llm` grader also fails a reply that asks for a ticket prefix or a
workspace location, which setup no longer asks about. Use `--judge-model
sonnet`: the default judge is a small model.

The free graders are calibrated by `tests/evals/check_grader_calibration.py` (above).
The `llm` graders have not been piloted, and neither has any case end to end:
that needs a host where `--allow-tools Bash` works (see artifacts/README.md).
Pilot with `--runs 1 --no-publish` first.

## Known limits — read before quoting a number

- **Explicit invocation is not reliably observable.** A typed `/acs:<skill>` can
  be expanded by the CLI before any model turn, in which case no `Skill` call
  happens and the grader reads 0x for a probe that routed. In the first full run
  `install-hooks` and `update` scored 1.00 and all six internal legs scored
  0.00. No invocation flag in the skills' frontmatter explains the split; it is
  unexplained, not diagnosed. Hence the `explicit` tag, and why the gate does
  not run it.
- **Three prompts were confounded** by context the empty workspace lacks:
  `route-create-design` (an epic ticket), `route-create-requirements` (an
  existing codebase), `route-docs-sync` (a finished change). Each prompt now
  states that context itself, and a one-turn run with only the Skill tool can
  neither look for it nor find it missing. That is a hypothesis until the next
  paid run measures it; each case's `description` keeps the history.
- **No routing number has been measured since the suite was re-cut.** The
  first full run predates the one-turn limit and 51 of the 90 cases. Treat
  every earlier rate as history, not a baseline.
- **Registration is not observable at all.** Whether the session lists the
  plugin's commands is decided before any model turn. There is no case for it.

## Not in CI

Nothing about this suite runs in CI — not the CLI, which spawns real sessions
that cost money (ADR-0022), and not the free checks either (ADR-0108). The
invariant is a grep that must return nothing:

```bash
grep -rn "run_evals\|evals/behavioural/\|plugin eval\|tests/evals" .github/workflows/
```

The free checks live in `tests/evals/`, named `check_*.py` so that CI's
`unittest discover -s tests` never loads them, and no test under `tests/acs/`
reads these case files:

| Check | Asserts |
|---|---|
| `check_cases.py` | every case and grader is well-formed; every shipped skill has a routing case and no case names one that does not ship; each routing regex matches its own skill and no neighbour; the routing conventions above hold |
| `check_grader_calibration.py` | every free setup and artifact grader passes an ideal run and fails a bad one |
| `check_gate.py` | `scripts/eval_gate.py` judges as the policy says, and the settings wire it |
| `check_probe_expectations.py` | the per-skill probe expectations earlier tickets pinned (create-docs, standardize-project, run-e2e-tests, setup), and this README's tag counts |
| `check_eval_changed.py` | `scripts/eval_changed.py` selects the right cases for a change and blocks only on what it should (against a fake `claude`) |

They run in two places:

- **The `acs-eval-checks` pre-commit hook** — when a commit touches this suite,
  a skill, the hook scripts, the schemas or the gate (`pre-commit install` once
  per clone). CI's pre-commit job `SKIP`s it.
- **The release gate's first step**, before anything is paid for.

By hand: `python3 -m unittest discover -s tests/evals -p 'check_*.py'`
(free, a few seconds).

## Running the evals your change affects

The cases your change affects run locally before you open a PR, on the Claude
subscription your `claude` CLI is logged in with. The `acs-evals` pre-commit
hook runs `scripts/eval_changed.py` on `git push`. It diffs your branch against
`origin/main`, finds the **skills you changed**, and runs only their cases,
**three times** each. It never runs the full suite: that is the release gate's
job. It is **on by default**:

```bash
pre-commit install --hook-type pre-push      # once per clone (also enables the branch/commit pre-push check)
claude plugin eval plugins/acs --case ignores-regex-request --runs 1 --ablation none   # once, in a terminal: trust this directory

python3 scripts/eval_changed.py --dry-run    # what your change would run (runs nothing)
pre-commit run acs-evals --hook-stage manual # run it now, without pushing
SKIP=acs-evals git push                      # skip it once
git config acs.evals false                   # turn it off for this clone (ACS_EVALS=0 for one push)
git config acs.evalsRuns 5                   # optional: runs per case (default 3)
git config acs.evalsBudget 40                # optional: runaway guard on computed cost (default $25)
```

| Your change | What it runs |
|---|---|
| a skill's frontmatter (`description`, `when_to_use`, …) | that skill's routing cases, and the cases whose `description` names it as `/acs:<skill>`: a `confusable` case that borrows its vocabulary, a `negative` or `control` case it could steal |
| any file of `setup`, `create-ticket` or `code` (for `setup`, also the setup wizard and the CI templates it installs) | that skill's behaviour cases |
| a skill's body, for a skill with no behaviour suite | nothing: routing reads only the frontmatter |
| an eval case, a fixture, `acs.py`, `acs_lib/`, anything else | nothing |

A description change runs four routing cases at the median. The most is eight,
for `code`, whose four legs each have a `negative` case. `setup` adds its eight
behaviour cases. The hook lists the eval cases your branch edited but did not
run, and the release gate runs them all. The two controls that name no skill,
`ignores-regex-request` and `ignores-unrelated-request`, run only there. To tie
a `negative` or `control` case to a skill, name the skill as `/acs:<skill>` in
the case's `description`.

It applies the [release gate's rules](#what-the-release-gate-passes) to the
skills your change touches, and runs the must-never cases first. **It blocks
the push** when:
- a selected `negative` or `control` case misroutes in any run;
- a touched skill's selected description cases, pooled, route less than 2/3 of
  their runs. A neighbour whose `confusable` case your new description steals
  counts too;
- a run could not happen: the directory is not trusted yet, a usage limit or
  auth failure hit mid-run, a case failed to load, or a run has no score;
- the budget guard stopped a gated routing case before it ran. An unmeasured
  case is not a pass.

`explicit` cases (not observable) and behaviour cases (graders not yet piloted)
below 1.0 are **reported**, with the command that re-runs them. They don't
block. Without `claude` on PATH the hook says so and lets the push through. The
budget is a guard against a runaway run, not a bill. Behaviour cases run last,
so a guard that trips usually stops only those, and they are listed as not run
without blocking.

The hook runs only at the `pre-push` and `manual` stages, which CI's pre-commit
job does not run, and the script exits at once when `CI` is set. It never passes
`--trust-plugin`: the CLI remembers trust per directory, so you confirm it once,
by hand.
