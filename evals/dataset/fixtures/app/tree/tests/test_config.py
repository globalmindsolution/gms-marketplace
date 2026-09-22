import unittest

from orders.config import load


class ConfigTest(unittest.TestCase):
    def test_defaults(self):
        s = load({})
        self.assertEqual((s.currency, s.tax_rate, s.store_path), ("EUR", 0.20, "data/store.json"))

    def test_env_overrides_and_bad_numbers_fail_loudly(self):
        self.assertEqual(load({"ORDERS_TAX_RATE": "0.07"}).tax_rate, 0.07)
        with self.assertRaises(ValueError):
            load({"ORDERS_TAX_RATE": "lots"})
