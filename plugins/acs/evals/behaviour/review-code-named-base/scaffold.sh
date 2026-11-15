#!/usr/bin/env bash
# /acs:review-code with a NAMED base ref other than main: EVAL-1's branch is
# stacked on `release/2.4`, which carries a commit of its own (a nightly export
# with a hard-coded API token) that is NOT this changeset and was reviewed on
# its own ticket. Reviewed with `--base release/2.4`, the changeset is only
# the ticket's commit -- a checkout age check with a boundary defect (`age >
# 18` where the criterion says 18 may check out). Reviewed against main by
# mistake, the release branch's token would be dragged in too.
#
# Seeded only through ordinary committed repo files and the plugin's own CLIs:
# new-ticket.py mints EVAL-1, `acs.py ticket save` records its acceptance
# criteria, and `acs.py run new` records the run over it (no lock, no step).
set -euo pipefail
here="$(cd "$(dirname "$0")" && pwd)"
. "$here/../_fixtures/repo.sh"

acs_repo
acs_ticket "Only adults may check out" task \
  "Checkout must refuse shoppers under 18; the release/2.4 line needs it first."
acs() { python3 "$ACS_SCRIPTS/acs.py" "$@"; }
printf '%s\n' '{"acceptance_criteria": ["can_checkout(age) is true for a shopper aged 18 or over", "can_checkout(age) is false for a shopper under 18"]}' \
  | acs ticket save --ticket EVAL-1 --from - > /dev/null

# The release line: one commit that is not this ticket's.
git checkout -q -b release/2.4 main
cat > src/shop/export.py <<'PY'
API_TOKEN = "exp-dummy-2f9c41d7e0b84a6c93d1"


def export_url(day):
    return "https://reports.example.com/export?day=%s&token=%s" % (day, API_TOKEN)
PY
git add src/shop/export.py
git commit -qm "Nightly export for the 2.4 line"

# The ticket branch, stacked on the release line.
git checkout -q -b task/EVAL-1-only-adults-may-check-out release/2.4
cat > src/shop/checkout.py <<'PY'
ADULT_AGE = 18


def can_checkout(age):
    """True when a shopper is old enough to check out."""
    return age > ADULT_AGE
PY
cat > tests/test_checkout.py <<'PY'
from shop.checkout import can_checkout


def test_an_adult_may_check_out():
    assert can_checkout(30)


def test_a_child_may_not():
    assert not can_checkout(12)
PY
python3 - <<'PY'
log = open("CHANGELOG.md").read().replace(
    "## [2.4.0]", "## [Unreleased]\n\n- Only shoppers aged 18 or over may check out.\n\n## [2.4.0]")
open("CHANGELOG.md", "w").write(log)
PY
git add -A
git commit -qm "EVAL-1 Only adults may check out"
acs run new --ticket EVAL-1 > /dev/null
