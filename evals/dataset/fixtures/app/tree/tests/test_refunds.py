import unittest
from datetime import date

from orders.payments.refunds import refund_order, refundable_cents
from tests._support import TODAY, service_in, tmpdir


class RefundPolicyTest(unittest.TestCase):
    def test_full_within_fourteen_days(self):
        self.assertEqual(refundable_cents(1000, date(2026, 6, 1), date(2026, 6, 15)), 1000)

    def test_restocking_fee_until_ninety_days(self):
        self.assertEqual(refundable_cents(1000, date(2026, 6, 1), date(2026, 6, 16)), 850)

    def test_nothing_after_ninety_days(self):
        self.assertEqual(refundable_cents(1000, date(2026, 1, 1), date(2026, 6, 15)), 0)

    def test_future_order_is_an_error(self):
        with self.assertRaises(ValueError):
            refundable_cents(1000, date(2026, 7, 1), date(2026, 6, 15))

    def test_refund_order_goes_through_the_gateway(self):
        _store, svc = service_in(tmpdir())
        order = svc.create("c1", [("TEE", 1)])
        svc.confirm(order.id)
        paid = svc.pay(order.id, TODAY)
        record = refund_order(svc.gateway, paid, 2400, TODAY, today=TODAY)
        self.assertEqual(record["status"], "refunded")
        self.assertIsNone(refund_order(svc.gateway, paid, 2400, date(2026, 1, 1), today=TODAY))
