"""Refund policy: full within the window, partial with a restocking fee after it."""

from datetime import date, timedelta

FULL_REFUND_DAYS = 14
RESTOCKING_PERCENT = 15


def refundable_cents(paid_cents, ordered_on, today):
    """What the customer gets back; zero once the order is older than 90 days."""
    age = today - ordered_on
    if age < timedelta(0):
        raise ValueError("an order cannot be refunded before it was placed")
    if age <= timedelta(days=FULL_REFUND_DAYS):
        return paid_cents
    if age <= timedelta(days=90):
        return paid_cents - paid_cents * RESTOCKING_PERCENT // 100
    return 0


def refund_order(gateway, order, paid_cents, ordered_on, today=None):
    today = today or date.today()
    amount = refundable_cents(paid_cents, ordered_on, today)
    if amount == 0:
        return None
    return gateway.refund(order.charge_id, amount)
