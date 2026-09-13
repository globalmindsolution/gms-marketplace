"""A charge gateway with idempotency keys and a recorded ledger of attempts."""

import hashlib


class PaymentDeclined(Exception):
    pass


class Gateway:
    """In-memory stand-in for a card processor; the same key never charges twice."""

    def __init__(self, store, decline_over_cents=100000):
        self.charges = store.section("charges")
        self.decline_over_cents = decline_over_cents

    @staticmethod
    def idempotency_key(order_id, amount_cents):
        return hashlib.sha256(("%s:%d" % (order_id, amount_cents)).encode()).hexdigest()[:16]

    def charge(self, order_id, amount_cents):
        if amount_cents <= 0:
            raise ValueError("charge amount must be positive")
        key = self.idempotency_key(order_id, amount_cents)
        existing = self.charges.get(key)
        if existing is not None:
            return dict(existing)
        if amount_cents > self.decline_over_cents:
            raise PaymentDeclined("amount %d exceeds the limit" % amount_cents)
        record = {"id": key, "order_id": order_id, "amount_cents": amount_cents,
                  "refunded_cents": 0, "status": "captured"}
        self.charges[key] = record
        return dict(record)

    def refund(self, charge_id, amount_cents):
        record = self.charges.get(charge_id)
        if record is None:
            raise KeyError("no charge %s" % charge_id)
        remaining = record["amount_cents"] - record["refunded_cents"]
        if amount_cents <= 0 or amount_cents > remaining:
            raise ValueError("refund of %d not within remaining %d" % (amount_cents, remaining))
        record["refunded_cents"] += amount_cents
        if record["refunded_cents"] == record["amount_cents"]:
            record["status"] = "refunded"
        return dict(record)
