#!/usr/bin/env bash
# The shared Python repo, set up long ago by an older acs whose settings file
# still carries two keys acs has since retired (acs_lib.RETIRED_SETTINGS_KEYS):
# `workspace_path`, which pointed pipeline state OUTSIDE the repo, and
# `prd_path` (documents are found, not configured -- ADR-0102). Unknown keys
# are legal and preserved, which is exactly why /acs:setup's Step 1 must name
# them from detect's `retired_keys` and say they are ignored.
#
# The file is written by hand on purpose: the older acs that wrote these keys
# no longer exists, and today's `setup apply` has no reason to write them.
# The CLI runs a scaffold in place, so $0 is this file in the case directory.
set -euo pipefail
here="$(cd "$(dirname "$0")" && pwd)"
. "$here/../_fixtures/repo.sh"

acs_repo
cat > .acs/settings.json <<'JSON'
{
  "ticket_prefix": "EVAL",
  "workspace_path": "../shop-acs-state",
  "prd_path": "docs/product/prd.md"
}
JSON
git add -A && git commit -qm "acs settings from an older acs"
