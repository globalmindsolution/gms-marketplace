#!/usr/bin/env bash
# analyze-requirements across two bounded contexts (ADR-0133): the shop repo
# with its PRD and architecture docs, plus two modules a refund-on-cancel
# change has to touch -- src/shop/orders.py (an order and its cancellation,
# with its own rules: only an unshipped order can be cancelled) and
# src/shop/payments.py (a card charge, and no refund yet). Story EVAL-1 is
# minted and given its PRD feature and acceptance criteria through the
# plugin's own CLIs. The analysis should come out as a folder with a README
# and one file per context -- order cancellation and payment refunds -- never
# as one long file.
# The CLI runs a scaffold in place, so $0 is this file in the case directory.
set -euo pipefail
here="$(cd "$(dirname "$0")" && pwd)"
. "$here/../_fixtures/repo.sh"

acs_repo
acs_prd
acs_architecture
cat > src/shop/orders.py <<'PY'
SHIPPED = "shipped"


class CannotCancel(Exception):
    pass


def cancel_order(order):
    """Cancel an order that has not shipped yet."""
    if order["status"] == SHIPPED:
        raise CannotCancel("a shipped order cannot be cancelled")
    order["status"] = "cancelled"
    return order
PY
cat > src/shop/payments.py <<'PY'
def charge(card_token, amount_cents):
    """Charge a card through the payments gateway; returns the charge id."""
    return {"charge_id": "ch_" + card_token[-4:], "amount_cents": amount_cents}
PY
git add -A && git commit -qm "Orders and payments"
acs_ticket "Refund the card when a paid order is cancelled" story \
  "Shoppers who cancel a paid order before it ships wait for us to refund them by hand. Cancelling a paid order should refund the card charge automatically."
printf '%s' '{"features": ["checkout-with-card-payments"], "acceptance_criteria": [
  "Cancelling an unshipped paid order refunds its card charge in full",
  "A shipped order still cannot be cancelled, and nothing is refunded",
  "A refund the payments gateway declines leaves the order cancelled and records the failed refund on it"
]}' | python3 "$ACS_SCRIPTS/acs.py" ticket save --ticket EVAL-1 --from - > /dev/null
