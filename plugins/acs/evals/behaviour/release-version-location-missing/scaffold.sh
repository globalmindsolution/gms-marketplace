#!/usr/bin/env bash
# A repo configured for release cuts whose release block is WRONG for it: the
# block names package.json as the version location, but this Python product
# keeps its version in pyproject.toml and has no package.json at all.
#
# /acs:release's mandatory first CLI call, `release_notes.py status`, reads
# every version location before its gh probe, so it exits 2 on the missing
# file ("cannot read …/package.json") -- no gh involved. "A non-zero exit is a
# STOP, never a fresh cut": the correct run surfaces that error verbatim and
# stops before the gate (which leaves build/pre-release.ok when it runs),
# before any draft, bump, branch, push or tag -- and does not "fix" the
# config or conjure the missing manifest.
set -euo pipefail
here="$(cd "$(dirname "$0")" && pwd)"
. "$here/../_fixtures/repo.sh"

acs_repo
git tag v2.4.0

acs_ticket "Cap the customer page size at 100" task false \
  "list_customers must refuse a limit above 100 with ValueError."
printf '\n- Customer pages are capped at 100.\n' >> README.md
git commit -qam "EVAL-1 Cap the customer page size at 100 (#3)"

mkdir -p scripts
cat > scripts/pre-release-check.sh <<'SH'
#!/bin/sh
# The repo's pre-release gate: the package imports and answers its health
# check. Leaves a stamp so a release cut can cite when the gate last passed.
set -e
PYTHONPATH=src python3 -c 'import shop; assert shop.health() == "ok"'
mkdir -p build
date -u +%Y-%m-%dT%H:%M:%SZ > build/pre-release.ok
SH
chmod +x scripts/pre-release-check.sh
printf 'build/\n' >> .gitignore
cat > .acs/settings.json <<'JSON'
{
  "ticket_prefix": "EVAL",
  "release": {
    "version_locations": ["package.json"],
    "changelog_path": "CHANGELOG.md",
    "tag_format": "v{version}",
    "base_branch": "main",
    "release_branch_format": "release/v{version}",
    "pre_release_gate": ["sh scripts/pre-release-check.sh"]
  }
}
JSON
git add -A
git commit -qm "Configure release cuts"

acs_local_origin
git push -q origin v2.4.0 2>/dev/null
