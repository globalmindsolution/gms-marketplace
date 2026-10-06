#!/usr/bin/env bash
# A repo correctly configured for release cuts (the version in package.json,
# a release block whose pre_release_gate is a committed check script that
# leaves build/pre-release.ok when it runs), with merged work since v2.4.0.
#
# The case is about the ARGUMENT, not the repo: the user asks for "2.5",
# which is not MAJOR.MINOR.PATCH. /acs:release fails fast on a version that
# does not match the semver shape "with a clear error naming the expected
# form -- do not guess a version from any file". So no 2.5.0 is inferred,
# and nothing is gated, drafted, bumped, branched, pushed or tagged.
set -euo pipefail
here="$(cd "$(dirname "$0")" && pwd)"
. "$here/../_fixtures/repo.sh"

acs_repo
printf '{\n  "name": "shop",\n  "version": "2.4.0"\n}\n' > package.json
git add -A
git commit -qm "Add package manifest"
git tag v2.4.0

acs_ticket "Cap the customer page size at 100" task \
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
