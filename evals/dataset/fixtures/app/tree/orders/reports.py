"""Revenue reporting over the charge ledger."""

from collections import defaultdict


def revenue_by_order(charges):
    """Net captured cents per order id, refunds subtracted."""
    totals = defaultdict(int)
    for record in charges.values():
        totals[record["order_id"]] += record["amount_cents"] - record["refunded_cents"]
    return dict(totals)


def summary(charges):
    per_order = revenue_by_order(charges)
    gross = sum(r["amount_cents"] for r in charges.values())
    refunded = sum(r["refunded_cents"] for r in charges.values())
    return {"orders": len(per_order), "gross_cents": gross,
            "refunded_cents": refunded, "net_cents": gross - refunded}


def render(summary_dict, currency):
    lines = ["orders:   %d" % summary_dict["orders"],
             "gross:    %.2f %s" % (summary_dict["gross_cents"] / 100, currency),
             "refunded: %.2f %s" % (summary_dict["refunded_cents"] / 100, currency),
             "net:      %.2f %s" % (summary_dict["net_cents"] / 100, currency)]
    return "\n".join(lines)
