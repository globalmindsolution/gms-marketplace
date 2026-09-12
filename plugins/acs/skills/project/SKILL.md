---
name: project
description: Set up a product repository's structure and tooling — auto-detects from declared on-disk evidence whether this repo is greenfield (no build manifest yet) or an existing codebase, states the mode it chose and the evidence for it, then runs the matching leg: a full greenfield scaffold (layout, build, test framework with coverage, lint, pre-commit, CI, a minimal green vertical slice), or an additive audit of an existing repo that only adds the missing docs, config and tooling and never rewrites source. Use to scaffold a fresh product repo after /acs:create-architecture, or to bring an existing repo up to acs's structural and tooling expectations.
argument-hint: "(no arguments)"
disallowed-tools: Edit, NotebookEdit
---

You are the coordinator of /acs:project — an unhooked umbrella, exactly like
`/acs:create-docs`, `/acs:ship`, and `/acs:release`: you have no
planner/executor/verifier of your own, you own no gate, and you never scaffold,
audit, or write a file yourself. You decide which of two internal legs this
repo needs — `create-project` (greenfield scaffold) or `standardize-project`
(additive audit of an existing repo) — state that decision and the evidence
behind it, and then invoke that one leg's own Start as a genuine Skill-tool
call, so every hook and gate it owns fires exactly as it would standalone.

Ground rules, non-negotiable:

- **The mode is not yours to reason out.** It is declared data plus a disk
  read: `acs_lib.project_mode(settings, checkout_root)` returns the mode and
  the evidence that decided it, from the `acs_lib.PROJECT_MODE_SETTINGS_KEY` /
  `acs_lib.PROJECT_MODE_SENTINEL` tables. You report its answer; you never
  re-derive one from the repo yourself, and you never overrule it.
- The leg's own hooks (pre/post), reflection cycle (planner/executor/verifier),
  gate, delivery ticket, branch, and PR all fire **unchanged**. You add
  orchestration only — you never bypass, simulate, or duplicate a hook.
- **Exactly one leg runs per invocation**, never both: a repo is either
  greenfield or it is not. The mode picks the leg; there is no fan-out here
  (that is `/acs:create-docs`'s mechanism, over independent doc sets that
  share no output).
- Each leg keeps its own SKILL.md, agents, hooks and gate and stays
  Skill-invocable. What the fold changed is that they are no longer
  *user-facing*: `/acs:project` is the entry point, and a leg is reached
  through it — or, for a resume, by naming that leg directly (see Resume).

## Start — mode detection

MANDATORY first action — resolve settings and the mode:

```bash
python3 - <<'PY'
import json, os, sys
sys.path.insert(0, os.path.join(os.environ["CLAUDE_PLUGIN_ROOT"], "hooks", "scripts"))
import acs_lib as lib
cwd = os.getcwd()
settings, _sources = lib.load_settings(cwd)
try:
    lib.validate_settings(settings, cwd)
except lib.GateError as exc:
    sys.stderr.write("acs project: %s\n" % exc)
    sys.exit(2)
root = lib.checkout_root(cwd) or cwd
decision = lib.project_mode(settings, root)
decision["checkout_root"] = root
decision["leg"] = lib.PROJECT_MODE_LEG[decision["mode"]]
print(json.dumps(decision, indent=2))
PY
```

**Exit 2.** When `lib.validate_settings` raises `GateError`, the snippet
catches it, writes the error to stderr, and exits 2: surface that stderr
verbatim and stop — settings are invalid or acs is not initialized here (the
same contract `ship/SKILL.md` and `create-docs/SKILL.md` use in their Start).

**Checkout root.** `project_mode` is given `lib.checkout_root(cwd)`, never the
raw `cwd`: every sentinel is resolved relative to that root, so a run started
from a repo subdirectory (or from a worktree) cannot read an existing project
as absent. This is the same resolution every gate uses — `build_context`
(`acs_lib/gates.py`) fills `ctx["checkout_root"]` from `checkout_root(cwd)`
(`acs_lib/repo.py`), and `create-docs/SKILL.md`'s Start does the same for
`fanout_batches`.

**What decided it.** `acs_lib.project_mode` is the **declared, not inferred**
mode predicate: `PROJECT_MODE_SENTINEL` names each piece of evidence that this
repo ALREADY has a project (a build manifest — `pyproject.toml`,
`package.json`, `go.mod`, …) and `PROJECT_MODE_SETTINGS_KEY` names the settings
key that resolves the directory it lives in (`null` = the checkout root
itself). It is the same settings-path + sentinel-file mechanism
`doc_set_present_on_disk` reads for the doc-bootstrap sets, through the same
presence primitive. Two directions, both pinned by tests:

- **no evidence at all → `bootstrap`** → the leg is `create-project`;
- **any evidence present → `standardize`** → the leg is `standardize-project`.

The partial case (some sentinels present, others absent) resolves the same way
as the full one: **any** present row means standardize. That is deliberate, and
it fails toward the safe leg — `standardize-project` only ever adds, and a
second run over an already-standardized repo finds nothing left to do, whereas
`create-project` on an existing codebase is refused by its own greenfield gate.

Widening the evidence — another stack's manifest, another marker — is a row in
**both** tables: a data change in `acs_lib`, never an edit to this skill.

**Report the decision before you dispatch.** State, in one short block: the
mode, the leg it selects, and the evidence rows that decided it (each row's
path, and whether it was found). `decision["reason"]` is already that sentence;
do not paraphrase it into something vaguer. A user who disagrees with the
verdict can say so — the leg they want is still Skill-invocable by name — but
you never silently substitute your own reading of the repo for the table's.

## Dispatch — one leg, a real Skill-tool call

Invoke the selected leg's own Start, and nothing else:

```
Skill(acs:create-project)          # mode: bootstrap
Skill(acs:standardize-project)     # mode: standardize
```

Exactly one of these runs. Each is a genuine Skill-tool call, so the real
`PreToolUse(Skill)` hook fires for that leg exactly as it would standalone —
the same precedent `/acs:ship` relies on ("/acs:ship is NOT a hooked skill, but
every step it invokes IS gated by pre/post hooks", `ship/SKILL.md`, Ground
rules) and `/acs:create-docs` relies on for its own legs. You never bypass,
simulate, or duplicate that leg's hooks: its own `pre-create-project.py` /
`pre-standardize-project.py` gate runs for real, its own Start mints its
delivery ticket, and its own `post-create-project.py` /
`post-standardize-project.py` finalizes the run for real.

Never invoke a leg from inside a spawned subagent (no acs subagent holds both
the Agent and Skill tools; decomposition stays the coordinator's job), and
never spawn a leg's agents yourself — the leg's own coordinator does that.

**Both legs share one precondition.** `gate_create_project` and
`gate_standardize_project` each check exactly `_require_architecture_doc_set`
(the architecture doc set — `hld/tech-stack.md` — must exist). If the selected
leg's Start exits non-zero, STOP and surface its stderr verbatim; never
improvise a substitute and never re-dispatch to the other leg to get past a
refusal — switching legs to dodge a gate is exactly the bypass this umbrella
must not perform. A missing architecture doc set refuses **either** leg, and
its stderr already says to run `/acs:create-architecture` first.

One specific case: on a fresh/unreconciled workspace partition, the leg's own
`--allocate` refuses with exit 2 and a ranked local-evidence reconciliation
proposal (`allocate_ticket_id`'s fail-closed gate) instead of minting its
delivery ticket id. Relay that stderr verbatim, obtain the confirmed start
number from the user — never invent it — and re-run that leg's Start with
`--seed-next <n>` added, exactly as the leg's own prose specifies.

**The leg's own second check is not redundant.** `create-project` re-verifies
greenfieldness itself before planning (`create-project/SKILL.md`'s Greenfield
gate), and it is the authority on its own refusal: the table above decides
which leg to *offer*, that gate decides whether the scaffold may *proceed*. If
it refuses, report its finding and stop — the evidence table is a documented
place to re-check, and a new marker row is how a repo like that becomes a
`standardize` verdict for the next run.

## After the leg returns

The leg owns its delivery ticket, its branch, its PR, its `pipeline-state.json`
(written under `flow: "product"` with its own step key) and its completion
report. You add nothing to them. Read only the compact result it hands back,
and render your own report (below) from the mode decision plus that result —
never from a re-read of the leg's phase artifacts, plans, or diffs.

## Resume

There is **no umbrella ledger of its own**: the leg's own
`pipeline-state.json` and its delivery ticket are the complete resume record. A
leg that failed, was interrupted, or was handed off resumes **exactly** like
any standalone run of that skill — never a re-invocation of this umbrella:

```
/acs:create-project
/acs:standardize-project <ticket-id>
```

Re-running `/acs:project` simply re-detects the mode from disk. Note that a
completed `create-project` run has by then produced a build manifest, so the
next `/acs:project` in that repo detects `standardize` — which is correct: the
scaffold exists, and what remains is an additive audit.

## Context pressure

Your own context carries the mode decision and one leg's compact result; the
leg's reflection loop runs in its own coordinator, not yours. If the leg hands
back a handoff instead of a result, relay its `continue_with` command verbatim
and stop.

## Completion report (normative)

Every terminal outcome ends your final message with the standard block
(INTERNALS.md "Completion report"):

```markdown
## /acs:project · <status>

- **Mode**: <bootstrap|standardize> → <leg invoked>
- **Evidence**: <the rows that decided it — path found, or "none found; checked <paths>">
- **Leg**: <ticket-id> — <status> — <PR url, or reason>
- **Findings**: <the leg's blocking finding, or "none">
- **Next**: <the leg's own resume command, if it did not complete>
```
