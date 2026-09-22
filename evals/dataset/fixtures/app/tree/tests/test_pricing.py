import unittest

from orders.discounts import Coupon
from orders.models import OrderLine
from orders.pricing import quote, subtotal, tax_cents


class PricingTest(unittest.TestCase):
    LINES = [OrderLine("MUG", 2, 1250), OrderLine("TEE", 1, 2000)]

    def test_subtotal_sums_lines(self):
        self.assertEqual(subtotal(self.LINES), 4500)

    def test_tax_rounds_half_up_on_the_cent(self):
        self.assertEqual(tax_cents(1, 0.20), 0)      # 0.2 cents
        self.assertEqual(tax_cents(3, 0.20), 1)      # 0.6 cents
        self.assertEqual(tax_cents(25, 0.20), 5)     # exactly 5.0
        self.assertEqual(tax_cents(1250, 0.20), 250)

    def test_quote_applies_coupon_before_tax(self):
        q = quote(self.LINES, 0.20, Coupon("TEN", percent=10))
        self.assertEqual(q, {"subtotal": 4500, "discount": 450, "tax": 810, "total": 4860})

    def test_quote_without_coupon(self):
        q = quote(self.LINES, 0.20)
        self.assertEqual((q["discount"], q["total"]), (0, 5400))
