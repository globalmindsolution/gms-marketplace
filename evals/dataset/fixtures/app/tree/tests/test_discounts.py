import unittest
from datetime import date

from orders.discounts import Coupon, CouponBook


class CouponTest(unittest.TestCase):
    def test_percent_and_fixed_are_exclusive(self):
        with self.assertRaises(ValueError):
            Coupon("BAD", percent=10, fixed_cents=100)

    def test_percent_out_of_range_is_refused(self):
        with self.assertRaises(ValueError):
            Coupon("BAD", percent=101)

    def test_fixed_never_exceeds_subtotal(self):
        self.assertEqual(Coupon("FIVER", fixed_cents=500).discount_cents(300), 300)

    def test_lookup_is_case_insensitive_and_window_bound(self):
        book = CouponBook()
        book.add(Coupon("Summer", percent=5, valid_from=date(2026, 6, 1), valid_to=date(2026, 8, 31)))
        self.assertIsNotNone(book.lookup("summer", date(2026, 7, 1)))
        self.assertIsNone(book.lookup("summer", date(2026, 9, 1)))
        self.assertIsNone(book.lookup("nope", date(2026, 7, 1)))
        self.assertIsNone(book.lookup("", date(2026, 7, 1)))
