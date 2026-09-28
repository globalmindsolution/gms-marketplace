#!/usr/bin/env bash
# The shared Python repo with an e2e suite (e2e/) already configured for acs
# as suites.e2e -- written through acs's own `setup apply`, with no CI gate,
# and committed. SKILL.md Step 2 offers the e2e merge gate "only when
# e2e/suites.e2e is already configured"; this is the case the setup/ suite
# never builds. Asked for that gate alone, setup installs .acs/ci/run-e2e.py
# and .github/workflows/acs-e2e.yml, names the `E2E suite` required check,
# and leaves the suite definition as it is.
# The CLI runs a scaffold in place, so $0 is this file in the case directory.
set -euo pipefail
here="$(cd "$(dirname "$0")" && pwd)"
. "$here/../_fixtures/repo.sh"

acs_repo
mkdir -p e2e
printf 'def test_health_over_http():\n    assert True\n' > e2e/test_health_e2e.py
python3 "$ACS_SCRIPTS/acs.py" setup apply --answers - >/dev/null <<'JSON'
{"settings": {"suites": {"e2e": {"command": "python3 -m pytest -q e2e"}}}, "ci": []}
JSON
git add -A && git commit -qm "e2e suite, configured for acs"
