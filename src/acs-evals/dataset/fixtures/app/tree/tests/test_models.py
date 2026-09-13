import unittest

from orders.models import Order, OrderLine, Product


class ModelTest(unittest.TestCase):
    def test_negative_price_is_refused(self):
        with self.assertRaises(ValueError):
            Product("X", "x", -1)

    def test_zero_quantity_is_refused(self):
        with self.assertRaises(ValueError):
            OrderLine("X", 0, 100)

    def test_order_round_trips_through_dict(self):
        order = Order(id="o1", customer_id="c1", lines=[OrderLine("MUG", 2, 1250)], coupon="TEN")
        again = Order.from_dict(order.to_dict())
        self.assertEqual(again, order)
        self.assertEqual(again.lines[0].quantity, 2)
