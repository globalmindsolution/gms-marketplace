# Artifact cases

Cases that assert what an acs skill **wrote** — workspace state, never the
model's prose. Tagged `artifacts`; the routing run (`--tag routing`) never picks
them up.

| Case | Asserts | From |
|---|---|---|
| `create-ticket-artifacts` | /acs:create-ticket mints a schema-complete task and indexes it | behavioural s02 |
| `resume-and-verify` | a fresh /acs:code session told only the ticket id finds and implements the seeded spec | behavioural s03 |

```bash
claude plugin eval . --tag artifacts --ablation none --scaffold --allow-tools Write Edit Bash
```

`--scaffold` runs each case's seed script; the Write/Edit/Bash grant is needed
because an acs skill's hooks and CLIs are shell. Granting Bash puts every
command under Claude Code's OS sandbox, and a host whose sandbox cannot
initialise refuses each run.

## What a seed has to do

Each of these was found by running the seed, not by reading about it:

- **Redirect `workspace_path` under the run directory.** acs keeps state
  OUTSIDE the repo tree by default, where no grader can read it.
  `.acs/settings.local.json` overrides it.
- **Fix the git remote.** acs derives its partition id from it (`owner-name`),
  so `https://github.com/example/shop.git` makes the path deterministically
  `.acs-workspace/example-shop/` and a grader can name it.
- **Seed a reconciled `counters.json`** (the MAR-402 fixture seam). A fresh
  partition otherwise refuses to allocate an id and asks for `--seed-next` —
  which a "do not ask me anything" prompt cannot answer.
- **Find the plugin from `$0`, never from `$PATH`.** The CLI runs a scaffold in
  place, so `$0` is its path in the case directory, and it passes no plugin-root
  variable. `$PATH` can carry an INSTALLED acs build's `bin/`, which would seed
  with the wrong build.

## What did not survive the migration

Stated so a green run is not read as more than it is:

- **create-ticket's two-phase gate check** — refuse while `plan.md` is missing,
  open once it exists — ran the gate CLI twice around a mid-test file write. A
  grader sees only the end state.
- **resume-and-verify's "verifier-clean"** — the create-pr brake opening. The
  verdict it reads lives at a path that depends on the iteration number, so no
  grader can name it.
- **resume-and-verify's PR-size cap** (≤ 400 changed lines) is a git diff count.
  No grader type computes one.
- **resume-and-verify seeds no plan.** v0.5.0 keeps a run's plan at
  `runs/<id>/steps/create-impl-plan/plan.md` behind a plan-approval brake that
  binds approval to the plan's bytes; placing one there by hand forges internal
  state. The gate reports "no plan for this run; /acs:code will work from the
  run's subject instead", and that is the path this case takes.

## Validation status

- **Both seeds are verified**: run by hand, each exits 0; `resume-and-verify`
  mints EVAL-1 through the plugin's own `new-ticket.py`, and the real
  `/acs:code` gate then OPENS on the seeded state (checked from outside the
  seed, which leaves no run lock behind).
- **Neither case has completed end to end.** In the cloud container this suite
  was built in, Bash is non-functional inside an eval run:

  ```
  apply-seccomp: write /proc/self/uid_map: Operation not permitted
  ```

  `bubblewrap` alone works there, so it is the eval run's own sandbox failing to
  initialise as root in a container. `create-ticket-artifacts` scored 0.25: the
  skill fired, and the three artifact graders threw `path ... does not exist`.
  Treat both cases as unvalidated until they have passed on a host where
  `claude plugin eval . --allow-tools Bash` works.
