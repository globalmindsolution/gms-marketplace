#!/usr/bin/env bash
# Seeds a task /acs:code can pick up WITHOUT spending a model call: a consumer
# repo, an acs workspace inside the run directory, a task minted through the
# plugin's own new-ticket CLI, and the spec the session must discover. Runs
# only under --scaffold.
#
# Deliberately NOT seeded, each for a measured reason:
#   * plan.md. v0.5.0 keeps a run's plan at
#     runs/<id>/steps/create-impl-plan/plan.md, behind a plan-approval brake
#     that binds approval to the plan's bytes. Dropping one there by hand forges
#     internal state; dropping it beside the ticket (where the old harness put
#     it) is never read -- the gate says "no plan for this run; /acs:code will
#     work from the run's subject instead", which is the path this case takes.
#   * a gate check. Running the real PreToolUse dispatcher to prove readiness
#     leaves runs/<id>/lock.json behind, held by no session the eval will have,
#     which can block the very run being graded. Readiness was checked by
#     running this script by hand instead (see ../README.md).
#
# The plugin is located from this script's own path, not from $PATH. Measured:
# the CLI runs a scaffold IN PLACE (so $0 is its path in the case directory)
# and passes no plugin-root variable -- while $PATH can carry an INSTALLED acs
# build's bin/, which would seed with the wrong build. Resolving from $0 always
# picks the build under test, including for a named installed target.
set -euo pipefail

PLUGIN="$(cd "$(dirname "$0")/../../.." && pwd)"
SCRIPTS="$PLUGIN/hooks/scripts"

git init -q
git remote add origin https://github.com/example/shop.git
git config user.email eval@example.com
git config user.name eval
printf 'def health():\n    return "ok"\n' > app.py

mkdir -p .acs .acs-workspace
cat > .acs/settings.json <<'JSON'
{
  "ticket_prefix": "EVAL",
  "test_coverage_percent": 90,
  "merge_strategy": "squash",
  "tracker": { "provider": "none" }
}
JSON
# acs keeps state OUTSIDE the repo by default; a grader can only read what
# lands under the run directory. The fixed remote above makes the partition id
# deterministically `example-shop`.
echo '{ "workspace_path": "./.acs-workspace" }' > .acs/settings.local.json
echo '.acs/settings.local.json' >> .gitignore
git add -A && git commit -qm seed

# A fresh partition refuses to allocate an id: acs's reconciliation guard will
# not restart a sequence it has no evidence for (it could collide with ids
# already in the repo's history). A reconciled counters.json is the documented
# fixture seam for that (MAR-402) -- without it the first mint blocks and asks
# for `--seed-next`, which a "do not ask me anything" prompt cannot answer.
mkdir -p .acs-workspace/example-shop
printf '{"next": 1, "reconciled": true, "seed_source": "explicit-user", "seeded_at": "%s"}\n' \
  "$(date -u +%Y-%m-%dT%H:%M:%SZ)" > .acs-workspace/example-shop/counters.json

python3 "$SCRIPTS/new-ticket.py" --title "Add a /health endpoint returning ok" \
  --type task --needs-design false > /dev/null

T=.acs-workspace/example-shop/EVAL-1
mkdir -p "$T/specs"
cat > "$T/specs/01-health.md" <<'MD'
# Spec 01 — GET /health

## Behavior
- Expose an HTTP endpoint `GET /health`.
- It responds `200` with the body exactly `ok`.
- The body must come from the existing `health()` function in `app.py`
  (single source of truth) — do not hard-code the `"ok"` literal elsewhere.

## Test plan
- An automated test asserts a `GET /health` request yields status `200` and
  body `ok`.
MD
