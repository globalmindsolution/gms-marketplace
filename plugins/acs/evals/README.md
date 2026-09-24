# acs eval suite

`claude plugin eval` cases for the acs plugin, in the layout
<https://code.claude.com/docs/en/plugin-evals> specifies. The case files **are**
the suite: there is no dataset they are rendered from and no generator to run.
Edit a case by editing its files.

```
evals/
├── routing/                  # 39 cases: does a prompt reach the right skill?
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
claude plugin eval . --case route-code --runs 1 --ablation none # one case, while iterating
claude plugin eval acs@gms-marketplace --tag routing --ablation none   # the INSTALLED build
claude plugin eval . --tag artifacts --scaffold --allow-tools Write Edit Bash   # see artifacts/README.md
claude plugin eval . --tag setup --scaffold --allow-tools Bash Write Edit --judge-model sonnet   # see below
```

Pin `--model` before recording a number you mean to compare with a later run:
unpinned, a model rollout is indistinguishable from a plugin regression.
`--max-cost-usd` is the cost lever, not a tight `max_turns`. A full routing run
is 39 cases × 3 runs at roughly $0.12 a run.

## Tags

| Tag | Cases | Asserts |
|---|---|---|
| `routing` | all 39 routing cases | a prompt reaches (or avoids) a skill |
| `description` | 24 | a natural-language request, never naming the skill, reaches it |
| `explicit` | 8 | a typed `/acs:<skill>` reaches it — see the limit below |
| `negative` | 6 | a description of an internal leg's subject does NOT reach the leg |
| `control` | 1 | an off-domain request invokes no skill at all |
| `artifacts` | 2 | the skill wrote the expected workspace state |
| `setup` | 8 | /acs:setup writes what was asked and nothing else; 2 of them assert it does not fire |

`--tag` keeps a case if ANY of its tags match, so `--tag description --tag
negative --tag control` runs the routing cases that are fully measurable.

## How routing is graded

Every routing case carries exactly one free, deterministic grader, so a case
score **is** the verdict: 1.00 routed as asserted, 0.00 did not. It is the
reference's canonical routing grader — `tool_used` on the `Skill` tool, with an
`input_match` regex naming the skill:

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

## Why `--ablation none`

It halves the spend, and for routing the baseline arm answers nothing: baseline
Claude has no acs skills, so it structurally never routes to one. It is a cost
choice, not a correctness one — `tool_used: Skill` graders are excluded from a
two-arm score, but only when a case has other graders to score, and every
routing case here has exactly one.

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

**Calibrated offline, not yet piloted.** Every free grader (regex,
`file_exists`) was run against the real scaffold plus an ideal run and a bad
run: each passes on the ideal run and at least one fails on the bad run. The
`llm` graders have not been piloted, and neither has any case end to end: that
needs a host where `--allow-tools Bash` works (see artifacts/README.md). Pilot
with `--runs 1 --no-publish` first.

## Known limits — read before quoting a number

- **Explicit invocation is not reliably observable.** A typed `/acs:<skill>` can
  be expanded by the CLI before any model turn, in which case no `Skill` call
  happens and the grader reads 0x for a probe that routed. In the first full run
  `install-hooks` and `update` scored 1.00 and all six internal legs scored
  0.00. No invocation flag in the skills' frontmatter explains the split; it is
  unexplained, not diagnosed. Hence the `explicit` tag.
- **Three prompts presuppose context the empty workspace lacks** —
  `route-create-design` (an epic ticket), `route-create-requirements` (an
  existing codebase), `route-docs-sync` (a finished change). Each case's
  `description` records the measured history. A miss on these is a confound
  until the context is seeded.
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
