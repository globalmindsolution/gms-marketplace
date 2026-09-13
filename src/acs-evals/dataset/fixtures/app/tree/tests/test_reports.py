import unittest

from orders.reports import render, revenue_by_order, summary


class ReportTest(unittest.TestCase):
    CHARGES = {
        "a": {"order_id": "o1", "amount_cents": 1000, "refunded_cents": 0},
        "b": {"order_id": "o1", "amount_cents": 500, "refunded_cents": 500},
        "c": {"order_id": "o2", "amount_cents": 2000, "refunded_cents": 300},
    }

    def test_revenue_by_order_nets_refunds(self):
        self.assertEqual(revenue_by_order(self.CHARGES), {"o1": 1000, "o2": 1700})

    def test_summary_and_render(self):
        s = summary(self.CHARGES)
        self.assertEqual(s, {"orders": 2, "gross_cents": 3500, "refunded_cents": 800, "net_cents": 2700})
        text = render(s, "EUR")
        self.assertIn("net:      27.00 EUR", text)
        self.assertIn("orders:   2", text)
