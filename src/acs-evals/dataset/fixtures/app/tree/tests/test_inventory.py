import unittest

from orders.inventory import Inventory, OutOfStock
from orders.storage import Store
from tests._support import tmpdir
import os


class InventoryTest(unittest.TestCase):
    def setUp(self):
        self.inv = Inventory(Store(os.path.join(tmpdir(), "s.json")))

    def test_receive_reserve_release(self):
        self.inv.receive("A", 3)
        self.assertEqual(self.inv.reserve("A", 2), 1)
        self.assertEqual(self.inv.release("A", 2), 3)

    def test_over_reservation_is_refused_and_leaves_stock_untouched(self):
        self.inv.receive("A", 1)
        with self.assertRaises(OutOfStock):
            self.inv.reserve("A", 2)
        self.assertEqual(self.inv.level("A"), 1)

    def test_non_positive_receipt_is_refused(self):
        with self.assertRaises(ValueError):
            self.inv.receive("A", 0)
