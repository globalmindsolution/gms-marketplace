# Behaviour cases

Cases asserting what each shipped skill **did** in a real session — the files
it wrote, the state it recorded through acs's own writers, the reply it gave —
never where a prompt routed (that is `../routing/`). Every skill has 2–7 cases
here, one per documented mode, branch or refusal (a resume, a no-op, a gate
that must refuse, an input that must stop for the user), and `setup`,
`create-ticket` and `code` also have `../setup/` and `../artifacts/`. GitHub
success paths are not cases: an eval run has no `gh` (ADR-0088). Tagged
`behaviour`.

```bash
# one case, one run, while authoring (needs a working Bash sandbox; see below)
claude plugin eval plugins/acs --case <name> --scaffold --allow-tools Bash Write Edit \
  --ablation none --judge-model sonnet --runs 1
python3 scripts/record_baseline.py <name>      # record its baseline (see below)
python3 -m unittest discover -s tests/evals -p 'check_*.py'   # free: shape, calibration
```

## Where they can run

A behaviour run grants Bash, and Claude Code runs every Bash command under its
OS sandbox. That needs `bubblewrap` and `socat` on Linux **and** unprivileged
user namespaces; on a host without them every command fails with
`apply-seccomp: write /proc/self/uid_map: Operation not permitted` and the case
cannot run. A Mac, or a Linux workstation, works. The Claude Code cloud
container does not (measured 2026-09-28). Nothing here runs in CI (ADR-0108).

## A case's files

| File | Holds |
|---|---|
| `prompt.md` | frontmatter `description`, `expected_outcome`, `tags: [behaviour]`, `max_turns`, `timeout_seconds`, `allowed_tools`; body: the request. It names the skill in prose ("Run the /acs:<skill> skill …") so the model calls the Skill tool — a typed `/acs:<skill>` line can be expanded before any model turn, and then no Skill call is observed. It states every choice the skill would ask about and says not to ask: an eval session cannot answer. |
| `case.yaml` | `schema_version: "1.1"`, `name` (= the directory), `context.scaffold_script: scaffold.sh` |
| `scaffold.sh` | executable; sources `../_fixtures/repo.sh` and calls its functions, then seeds anything else ONLY through the plugin's own CLIs (`acs.py`, `new-ticket.py`) — never a hand-forged state file |
| `graders/skill-fired.md` | `tool_used` on `Skill`, `input_match: '"skill"\s*:\s*"(?:[\w-]+:)?<skill>"'`, `min: 1` — the one grader that names the case's skill |
| `graders/*.md` | at least one FREE grader on what the run produced (`file_exists`, or `regex` on `{ source: file, path: … }`, `files` or `last_message`) that a bad run fails; optionally an `llm` grader on the reply |
| `calibration.py` | `IDEAL(ws)` and `BAD = {label: play}` — see below |
| `baseline.criteria.md` | the `baseline` grader's criteria: `PASS if, like the reference, …` / `FAIL if …` |
| `baseline.jsonl` + `graders/matches-baseline.md` | written only by `scripts/record_baseline.py`, together |

Grader rules worth knowing (read out of claude 2.1.281): `files` and
`file_exists` see only paths the run **created**, not ones it modified or the
scaffold made; a `regex` on a file that does not exist fails in every match
mode, `not_contains` included.

## Calibration (free)

`tests/evals/check_grader_calibration.py` builds the case's real scaffold in a
temp directory and plays `IDEAL` and each `BAD` through a `Workspace`:
`ws.skill(name)` records a Skill call, `ws.acs(*args)` runs the plugin's
`acs.py`, `ws.sh(cmd)` runs a shell command, `ws.write(rel, text)` writes a
file, `ws.reply = "…"` sets the final message. It then grades every free grader
the way the CLI does. The ideal run must pass all of them; each bad run must
fail at least one. Make `IDEAL` do what the skill really does, through its real
writers where they exist, so a change to what the skill writes fails here for
free before it fails a paid run.

## The baseline grader

`type: baseline` has a judge decide whether a run meets the criteria **at least
as well as** a reference transcript. The reference is a real, clean run of the
case: `scripts/record_baseline.py <case>` runs it once, refuses it unless every
grader passed and nothing but the turn limit errored, then writes
`baseline.jsonl` and `graders/matches-baseline.md` from `baseline.criteria.md`.
Until a case is recorded it has no baseline grader, because the CLI refuses a
case whose `baseline_file` is missing. Read a transcript before committing it:
it is a real session.

## GitHub

A run has no network and no `gh` credentials. `acs_local_origin` gives the run
a bare repository standing in for GitHub, so `git push` and `git fetch` work
while the remote URL (and acs's repo identity) stays
`https://github.com/example/shop.git`. A skill that needs the forge itself
(opening, reading or merging a PR) meets `gh` failing; acs surfaces that as a
classified finding and never routes around it (ADR-0088), and that — plus
whatever the skill correctly did locally first — is what its case asserts.
