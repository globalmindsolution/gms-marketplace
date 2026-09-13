import os
import unittest

from orders.payments.gateway import Gateway, PaymentDeclined
from orders.storage import Store
from tests._support import tmpdir


class GatewayTest(unittest.TestCase):
    def setUp(self):
        self.gw = Gateway(Store(os.path.join(tmpdir(), "s.json")), decline_over_cents=5000)

    def test_same_order_and_amount_charge_once(self):
        first = self.gw.charge("o1", 1200)
        second = self.gw.charge("o1", 1200)
        self.assertEqual(first, second)
        self.assertEqual(len(self.gw.charges), 1)

    def test_different_amount_is_a_new_charge(self):
        self.gw.charge("o1", 1200)
        self.gw.charge("o1", 1300)
        self.assertEqual(len(self.gw.charges), 2)

    def test_over_limit_is_declined_and_not_recorded(self):
        with self.assertRaises(PaymentDeclined):
            self.gw.charge("o2", 9000)
        self.assertEqual(len(self.gw.charges), 0)

    def test_non_positive_amount_is_refused(self):
        with self.assertRaises(ValueError):
            self.gw.charge("o3", 0)

    def test_refund_bounds_and_status(self):
        charge = self.gw.charge("o4", 1000)
        self.gw.refund(charge["id"], 400)
        with self.assertRaises(ValueError):
            self.gw.refund(charge["id"], 700)
        final = self.gw.refund(charge["id"], 600)
        self.assertEqual(final["status"], "refunded")
        with self.assertRaises(KeyError):
            self.gw.refund("nope", 1)
