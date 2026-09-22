import unittest

from orders.inventory import OutOfStock
from orders.orders import InvalidTransition
from tests._support import TODAY, service_in, tmpdir


class OrderServiceTest(unittest.TestCase):
    def setUp(self):
        self.store, self.svc = service_in(tmpdir())

    def test_create_reserves_stock_and_quotes(self):
        order = self.svc.create("c1", [("MUG", 2), ("TEE", 1)], coupon="TEN")
        self.assertEqual(self.svc.inventory.level("MUG"), 8)
        self.assertEqual(self.svc.quote(order, TODAY)["total"], 4860)

    def test_unknown_sku_is_refused_before_any_reservation(self):
        with self.assertRaises(KeyError):
            self.svc.create("c1", [("NOPE", 1)])
        self.assertEqual(self.svc.inventory.level("MUG"), 10)

    def test_out_of_stock_surfaces(self):
        with self.assertRaises(OutOfStock):
            self.svc.create("c1", [("TEE", 6)])

    def test_life_cycle_and_payment(self):
        order = self.svc.create("c1", [("MUG", 1)])
        self.svc.confirm(order.id)
        paid = self.svc.pay(order.id, TODAY)
        self.assertEqual(paid.status, "paid")
        self.assertTrue(paid.charge_id)
        self.assertEqual(self.store.section("charges")[paid.charge_id]["amount_cents"], 1500)

    def test_paying_a_draft_is_invalid(self):
        order = self.svc.create("c1", [("MUG", 1)])
        with self.assertRaises(InvalidTransition):
            self.svc.pay(order.id, TODAY)

    def test_cancel_releases_stock_and_is_terminal(self):
        order = self.svc.create("c1", [("MUG", 3)])
        self.svc.cancel(order.id)
        self.assertEqual(self.svc.inventory.level("MUG"), 10)
        with self.assertRaises(InvalidTransition):
            self.svc.confirm(order.id)

    def test_missing_order(self):
        with self.assertRaises(KeyError):
            self.svc.get("nope")
