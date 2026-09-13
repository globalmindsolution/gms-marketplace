# Tier 2 — agentic routing cases (`claude plugin eval`)

One probe per acs skill, in Claude Code's official plugin-eval format. This is
the half of the golden dataset that needs a real model: whether a natural
request actually *routes* to the right skill.

## Status: authored, never executed

**No case in this directory has ever been run.** `claude plugin eval` is an
early-access feature and was not enabled on the account this dataset was built
with:

```
$ claude plugin eval init --bare sample
`plugin eval` is currently in early access
```

So the case fields and grader shape below are authored from
`claude plugin eval --help` on Claude Code 2.1.263 — the documented surface —
not from a passing run. **Validate the schema before trusting any result:**

```bash
claude plugin eval acs --case route-code --runs 1
```

If the grader shape is wrong, fix it in `runner/gen_plugin_eval.py` and
regenerate. Do not patch the YAML by hand — it is overwritten.

## These files are generated

`dataset/routing.json` is the source of truth. It holds the curated prompts and
the skill each must (or must not) route to.

```bash
python3 runner/gen_plugin_eval.py           # render evals/routing/**/case.yaml
python3 runner/gen_plugin_eval.py --check   # fail if the tree is stale
```

## What the 27 probes cover

25 skills, 27 probes:

- **23 model-invocable skills** — one natural-language request each, phrased the
  way a user would actually ask and **never naming the skill**. Naming it would
  test string matching rather than routing.
- **2 user-only skills** (`install-hooks`, `update`, both
  `disable-model-invocation: true`) — a **pair** each: an explicit `/acs:<skill>`
  invocation that must route, plus a bare description of the skill's intent that
  must **not**. The negative probe is the one that matters: it is the only thing
  that tests the no-auto-invoke guarantee, and a plugin that quietly starts
  auto-invoking `update` would pass every positive probe.

## Running

```bash
claude plugin eval acs                       # every case
claude plugin eval acs --tag routing         # by tag
claude plugin eval acs --tag negative        # just the no-auto-invoke probes
claude plugin eval acs --case 'route-code'   # one case
claude plugin eval acs --runs 1              # cheaper, noisier
```

Routing is non-deterministic, so cases default to `runs: 3`. `max_turns: 2`
keeps each probe to roughly the time-to-route — these cases assert on *which
skill was selected*, never on what the skill body then did.

Ablation (`--ablation with-without`, the default when a plugin resolves) is
worth having here: a positive probe that passes without the plugin installed is
not evidence the plugin routed anything.

## What is NOT here

The routing surface that can be checked **without** a model — that all 25 skills
ship, carry a non-empty `description`, and declare the right
`disable-model-invocation` — is pinned in tier 1 instead, as the `SKILL-*` cases
in `dataset/cases/10-skills.json`. That tier runs today, costs nothing, and
catches the packaging failures this tier would only find by spending sessions.
