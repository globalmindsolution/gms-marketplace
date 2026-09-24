# acs eval suite

`claude plugin eval` cases for the acs plugin, in the layout
<https://code.claude.com/docs/en/plugin-evals> specifies. The case files **are**
the suite: there is no dataset they are rendered from and no generator to run.
Edit a case by editing its files.

```
evals/
├── routing/                  # 90 cases: does a prompt reach the right skill?
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
`--max-cost-usd` is the cost lever. A routing run is one model turn (see below);
what that costs per run has not been measured yet. The last measured figure,
about $0.12 a run, was taken with ten turns allowed.

## Tags

| Tag | Cases | Asserts |
|---|---|---|
| `routing` | all 90 routing cases | a prompt reaches (or avoids) a skill |
| `description` | 72 | a natural-language request, never naming the skill, reaches it — three phrasings for each of 24 skills |
| `confusable` | 24 | (a subset of `description`) the phrasing borrows a neighbouring skill's vocabulary |
| `explicit` | 8 | a typed `/acs:<skill>` reaches it — see the limit below |
| `negative` | 6 | a description of an internal leg's subject does NOT reach the leg |
| `control` | 4 | a request answered in prose invokes no skill at all |
| `artifacts` | 2 | the skill wrote the expected workspace state |
| `setup` | 8 | /acs:setup writes what was asked and nothing else; 2 of them assert it does not fire |

`--tag` keeps a case if ANY of its tags match, so `--tag description --tag
negative --tag control` runs the routing cases that are fully measurable —
which is exactly what the release gate runs.

Each of the 24 skills a user reaches by describing the work has three
phrasings: the plain request, an indirect one with the context stated in the
prompt, and a `confusable` one that borrows a neighbour's words — "don't merge
anything, just open the pull request", "not a design for one ticket: regenerate
the product-wide C4 views". Each confusable case's `description` names the
neighbour. One prompt per skill measured one sentence; three measure the
description.

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

1. `python3 -m unittest tests.acs.test_eval_cases tests.acs.test_eval_gate` —
   free: a malformed case fails before anything is spent.
2. `claude plugin eval plugins/acs --tag description --tag negative --tag
   control --ablation none --threshold 0 --json …` — the paid run. `--threshold
   0` stops the CLI from judging; the result goes to a file.
3. `python3 scripts/eval_gate.py <that file> --min-skill-rate 2/3
   --min-suite-rate 9/10` — the judgement.

The CLI judges one case at a time: it exits 1 if any case scores below
`--threshold`, which defaults to 1.0. For routing that is the wrong unit. The
model is stochastic, so a skill that routes right 90% of the time scores 3/3
on a prompt only 73% of the time, and across the 72 description cases the
chance that every one scores 3/3 is effectively nil. A gate at 1.0 fails on
almost every run whether or not anything is wrong. The old gate was also
unpassable for a second reason: it ran the `explicit` cases, six of which
scored 0.00 in the first full run for a reason no grader can see.

`scripts/eval_gate.py` applies this policy instead:

| Kind | Rule | Why |
|---|---|---|
| `negative`, `control` | every run must pass | pulling a request onto an internal leg, or firing a skill on a git question, is a defect however rarely it happens |
| `description` | each **skill**, pooling its three phrasings (9 runs), routes at least **2/3**; the **suite** routes at least **9/10** | the floor catches a broken skill, the suite rate a broad slide where no single skill is broken |
| `explicit` | not gated | not observable — see the limit below |

It fails closed on anything it cannot read: a partial run (cost ceiling hit), an
unknown result format, a case it cannot map to a skill, a gated case missing
from the run, or a result older than six hours. The CLI only warns when it
cannot write `--json`, so without that last check a stale file from an earlier
run could be judged in place of this one.

**The two rates are provisional.** They were chosen before any run of this
suite, from the arithmetic above. Re-set them from the first full three-run
baseline (Phase 2 below). A rate is only worth what the baseline behind it is.

## How the graders are shown to be right

A grader is trusted only after it has passed four checks. Two are free and run
on every PR. Two are paid and **have not been done yet**.

| Check | What it proves | Where | Status |
|---|---|---|---|
| Well-formed | every case and grader uses keys and values the CLI accepts; every routing regex matches its own skill, bare and qualified, and no other shipped skill | `tests/acs/test_eval_cases.py` | free, every PR |
| Calibrated | every free grader in `setup/` and `artifacts/` passes an ideal run and at least one fails each bad run, built from the case's real scaffold and the plugin's real writers and graded the way the CLI grades | `tests/acs/test_eval_grader_calibration.py` | free, every PR |
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
4. Take the three-run baseline that sets the gate's rates.

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

The free graders are calibrated by `test_eval_grader_calibration.py` (above).
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

ADR-0022: behavioural and LLM evals never run in CI, and these cases spawn real
sessions that cost money. The invariant is a grep that must return nothing:

```bash
grep -rn "run_evals\|evals/behavioural/\|plugin eval" .github/workflows/
```

What does run free on every PR is `tests/acs/test_eval_cases.py`, which parses
these files and checks their shape and coverage: every shipped skill has a
case, no case names a skill that is not shipped, every grader is well-formed.
The CLI itself never runs in CI, so that test is the only thing that catches a
malformed case before someone pays to discover it.
`test_eval_grader_calibration.py` and `test_eval_gate.py` run free beside it.
