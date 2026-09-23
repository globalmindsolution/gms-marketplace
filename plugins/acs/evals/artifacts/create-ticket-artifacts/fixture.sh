#!/usr/bin/env bash
# Seeds the empty eval workspace with a throwaway consumer repo and an acs
# workspace INSIDE it. Runs only under --scaffold.
#
# Two things make this gradeable, and both are load-bearing:
#
#   * settings.local.json redirects `workspace_path` under the run's own
#     directory. acs keeps pipeline state OUTSIDE the repo tree by default,
#     which would put every artifact somewhere no grader can read.
#   * the git remote is fixed, so the partition id acs derives from it
#     (owner-name, via acs_lib.repo_partition_id) is deterministically
#     `example-shop` and a grader can name the path.
set -euo pipefail

git init -q
git remote add origin https://github.com/example/shop.git
git config user.email eval@example.com
git config user.name eval

printf 'def health():\n    return "ok"\n' > app.py

mkdir -p .acs
cat > .acs/settings.json <<'JSON'
{
  "ticket_prefix": "EVAL",
  "test_coverage_percent": 90,
  "merge_strategy": "squash",
  "tracker": { "provider": "none" }
}
JSON
cat > .acs/settings.local.json <<'JSON'
{ "workspace_path": "./.acs-workspace" }
JSON
echo '.acs/settings.local.json' >> .gitignore
mkdir -p .acs-workspace

# A fresh partition refuses to allocate an id: acs's reconciliation guard will
# not restart a sequence it has no evidence for (it could collide with ids
# already in the repo's history). A reconciled counters.json is the documented
# fixture seam for that (MAR-402) -- without it the first mint blocks and asks
# for `--seed-next`, which a "do not ask me anything" prompt cannot answer.
mkdir -p .acs-workspace/example-shop
printf '{"next": 1, "reconciled": true, "seed_source": "explicit-user", "seeded_at": "%s"}\n' \
  "$(date -u +%Y-%m-%dT%H:%M:%SZ)" > .acs-workspace/example-shop/counters.json

git add -A
git commit -qm seed
