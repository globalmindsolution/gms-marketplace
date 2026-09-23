# Artifact-level cases

Cases that assert what an acs skill **wrote**, not where a prompt routed. The
assertion target is workspace state, never the model's prose. Migrated from the
behavioural harness's `s02` scenario.

They are **not** part of `make -C evals routing-cases`, which filters
`--case 'route-*'`. Run them deliberately:

```bash
make -C evals artifact-cases
```

## They need more than the routing cases do

- `--scaffold`, to run each case's `fixture.sh` in the empty workspace.
- `--allow-tools Write Edit Bash`, because an acs skill's hooks and CLIs are
  shell. Everything beyond the read-only set needs an operator grant.
- A host where the eval run's sandbox can initialise. Granting Bash puts every
  command under Claude Code's OS sandbox, and **a machine with no working
  backend refuses each run** rather than running it unconfined.

## What the fixture has to do, and why

Two lines in `fixture.sh` are load-bearing, and a case that drops either grades
nothing:

- **`workspace_path` is redirected under the run directory.** acs keeps pipeline
  state OUTSIDE the repo tree by default, which puts every artifact somewhere no
  grader can read. `settings.local.json` overrides it.
- **The git remote is fixed.** acs derives its partition id from the remote
  (`owner-name`, via `acs_lib.repo_partition_id`), so a fixed remote makes the
  path deterministic — `https://github.com/example/shop.git` gives
  `.acs-workspace/example-shop/`, which a grader can name.

Verified on 2026-09-23: the scaffold runs in the agent's own cwd, the redirect
holds, and acs created `.acs-workspace/example-shop/` at exactly that path. The
design is sound.

## Known blocker in a container

In this repo's cloud session the case scores 0.25: `create-ticket-fired` passes
and the three artifact graders throw `path ... does not exist`, because **Bash
is non-functional inside the eval run**:

```
apply-seccomp: write /proc/self/uid_map: Operation not permitted
```

`bubblewrap` alone works there, so this is the eval run's own sandbox runtime
failing to initialise as root inside a container, not a missing backend. Every
acs skill needs shell, so no artifact case can complete. Run these on a host
where `claude plugin eval . --allow-tools Bash` works; a 0.25 with three
`does not exist` graders and that message in the trace is the blocker, not a
regression in the plugin.
