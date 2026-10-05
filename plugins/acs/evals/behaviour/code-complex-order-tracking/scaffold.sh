#!/usr/bin/env bash
# /acs:code on a ticket whose plan records `delivery_path: complex` and whose
# approval is current, so /acs:code must dispatch to the code-complex leg (a
# real Skill call the grader sees): one implementer per partition, then the
# integration implementer over the seam between them.
#
# The plan is produced the way /acs:create-impl-plan produces one, through the
# plugin's own writers wherever one exists:
#   acs.py step start --step create-impl-plan   (run, lock, pointer, ledger)
#   the draft at runs/EVAL-1/steps/create-impl-plan/plan.md -- the ONE file
#     plan-approval.py and /acs:code read; the planner subagent writes it with
#     the Write tool, so there is no CLI writer for its bytes
#   acs.py filemap set --skill code --iteration 1 (the map the guard enforces)
#   the published copy in docs/development/<feature>/EVAL-1/, left uncommitted on main
#   post-create-impl-plan.py (finishes the step, releases the lock)
# and then APPROVED the way a human approves it: `acs.py plan check`, the sole
# writer of plan-approval.json, which hashes the plan's bytes. Nothing here
# writes the approval record by hand; an edited plan would be unapproved.
set -euo pipefail
here="$(cd "$(dirname "$0")" && pwd)"
. "$here/../_fixtures/repo.sh"

acs_repo
ACS_FEATURES=order-tracking
acs_ticket "Track order status for shoppers" story false \
  "Orders move placed -> paid -> shipped -> delivered and never backwards; shoppers see a friendly label for each status."
acs() { python3 "$ACS_SCRIPTS/acs.py" "$@"; }
printf '%s\n' '{"acceptance_criteria": ["advance(order, status) moves an order one step forward: placed, paid, shipped, delivered", "advance refuses a backward or skipped transition with ValueError", "tracking_label(status) gives a shopper-facing label for every status an order can have"]}' \
  | acs ticket save --ticket EVAL-1 --from - > /dev/null

acs step start --step create-impl-plan --ticket EVAL-1 > /dev/null 2>&1
draft="$ACS_PARTITION/runs/EVAL-1/steps/create-impl-plan/plan.md"
cat > "$draft" <<'MD'
# Plan — EVAL-1 Track order status for shoppers

Two components that must agree: the order lifecycle (merchant side) and the
shopper-facing tracking view. Each is its own partition; they meet at one
seam, the set of statuses.

## Approach

**Task 1 — orders.** `src/shop/orders.py` defines
`STATUSES = ("placed", "paid", "shipped", "delivered")`, an `Order` with a
`status` starting at `placed`, and `advance(order, status)`, which moves the
order exactly one step forward and raises `ValueError` on any backward or
skipped transition. A shipped order is never un-shipped: the transition is
irreversible by design.

**Task 2 — tracking.** `src/shop/tracking.py` defines
`tracking_label(status)`, mapping each status to what a shopper reads
("Order received", "Payment confirmed", "On its way", "Delivered"), and
raising `KeyError` for a status it does not know.

**The seam.** Tracking must label every status orders can produce. Neither
partition may edit the other's files, so the integration implementer owns the
seam: it makes `tracking` derive its table from `orders.STATUSES` and adds
`tests/test_order_tracking.py`, asserting every status in `STATUSES` has a
label.

Rejected: one module for both, because merchants and shoppers change them for
different reasons.

## Test strategy

- Task 1, `tests/test_orders.py`, written first: forward steps pass (AC-1);
  backward and skipped transitions raise `ValueError` (AC-2).
- Task 2, `tests/test_tracking.py`, written first: each known status has its
  label; an unknown status raises `KeyError` (AC-3).
- Integration, `tests/test_order_tracking.py`: every `STATUSES` entry has a
  label (AC-3 across the seam).

Run: `python3 -m pytest -q tests/test_orders.py tests/test_tracking.py
tests/test_order_tracking.py`. Coverage target: 90% of both modules, measured
by the review's final gate.

## Risks

- The transition rule is irreversible for a shopper: a wrong rule ships
  orders twice or strands them. The review should read `advance` hardest.
- The seam: a status added to `orders` without a label breaks the shopper
  view. The integration test is what guards it.

## Contract
delivery_path: complex
owes:
  api_contract: false
  test_cases: false
  e2e: false
  reason: "library modules only; no HTTP surface and no browser flow in this change"

### Executor tasks & file map
- task 1: src/shop/orders.py, tests/test_orders.py
- task 2: src/shop/tracking.py, tests/test_tracking.py
MD
acs filemap set --skill code --iteration 1 --task 1 \
  --file src/shop/orders.py --file tests/test_orders.py > /dev/null
acs filemap set --skill code --iteration 1 --task 2 \
  --file src/shop/tracking.py --file tests/test_tracking.py > /dev/null
mkdir -p docs/development/order-tracking/EVAL-1
cp "$draft" docs/development/order-tracking/EVAL-1/plan.md
result="$ACS_PARTITION/runs/EVAL-1/steps/create-impl-plan/result.json"
cat > "$result" <<'JSON'
{"status": "completed", "summary": "plan published; two disjoint executor tasks and one seam",
 "states": {"plan_path": "docs/development/order-tracking/EVAL-1/plan.md", "plan_approved": false,
            "file_map": {"1": ["src/shop/orders.py", "tests/test_orders.py"],
                         "2": ["src/shop/tracking.py", "tests/test_tracking.py"]}},
 "findings": [], "errors": []}
JSON
python3 "$ACS_SCRIPTS/post-create-impl-plan.py" --result-file "$result" > /dev/null 2>&1
# The human's approval, through its sole writer. Refuse to seed an unapproved
# deep-path plan: the case would then measure the pre-hook, not the leg.
# (Captured first: `| grep -q` under pipefail can SIGPIPE the writer.)
checked="$(acs plan check --run EVAL-1)"
grep -q '"plan_approved": true' <<<"$checked"
