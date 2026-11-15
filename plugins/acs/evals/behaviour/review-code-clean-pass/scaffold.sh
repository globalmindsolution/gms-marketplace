#!/usr/bin/env bash
# /acs:review-code on a ticket whose changeset -- uncommitted on main, as
# /acs:code leaves it (ADR-0127) -- is CLEAN: a negative
# page offset is refused with ValueError, every acceptance criterion has a
# test, the CHANGELOG records it and the README states it. Nothing is wrong,
# so no candidate finding should survive adjudication, stage 3's gate (build,
# lint, the full unit suite, coverage) runs, and the kernel derives a pass.
#
# Seeded only through ordinary repo files and the plugin's own CLIs:
# new-ticket.py mints EVAL-1, `acs.py ticket save` records its acceptance
# criteria, and a `code` step opened with `acs.py step start` and closed with
# post-code.py brackets the change (no lock left held).
set -euo pipefail
here="$(cd "$(dirname "$0")" && pwd)"
. "$here/../_fixtures/repo.sh"

acs_repo
acs_ticket "Reject a negative page offset" task \
  "list_customers(offset=-3) silently returns a page instead of refusing the offset."
acs() { python3 "$ACS_SCRIPTS/acs.py" "$@"; }
printf '%s\n' '{"acceptance_criteria": ["list_customers(offset=-1) raises ValueError", "list_customers(offset=0) still returns the first page"]}' \
  | acs ticket save --ticket EVAL-1 --from - > /dev/null

# /acs:code's step, opened before the change it leaves behind: its start
# records the run's baseline (ADR-0127) on the clean tree, so the change
# below is the run's changeset, uncommitted on main as /acs:code leaves it.
acs step start --step code --ticket EVAL-1 > /dev/null 2>&1
cat > src/shop/__init__.py <<'PY'
PAGE_SIZE = 20


def health():
    return "ok"


def list_customers(offset=0, limit=PAGE_SIZE):
    # a negative offset is a caller bug, never a page
    if offset < 0:
        raise ValueError("offset must be >= 0")
    return {"items": [], "offset": offset, "limit": limit}
PY
cat > tests/test_list_customers.py <<'PY'
"""list_customers refuses a negative offset (EVAL-1)."""
import pytest

from shop import list_customers


def test_a_negative_offset_is_refused():
    with pytest.raises(ValueError):
        list_customers(offset=-1)


def test_offset_zero_is_the_first_page():
    assert list_customers(offset=0) == {"items": [], "offset": 0, "limit": 20}
PY
python3 - <<'PY'
readme = open("README.md").read().replace(
    "lists customers, 20 per page by default.",
    "lists customers, 20 per page by default; a negative offset is refused.")
open("README.md", "w").write(readme)
log = open("CHANGELOG.md").read().replace(
    "## [2.4.0]", "## [Unreleased]\n\n- A negative page offset is refused.\n\n## [2.4.0]")
open("CHANGELOG.md", "w").write(log)
PY
python3 "$ACS_SCRIPTS/post-code.py" > /dev/null <<'JSON'
{"status": "completed", "summary": "implemented; nothing committed (ADR-0127)",
 "findings": [], "errors": []}
JSON
