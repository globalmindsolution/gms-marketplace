import json
import os
import unittest

from orders.storage import Store
from tests._support import tmpdir


class StoreTest(unittest.TestCase):
    def test_missing_file_starts_empty(self):
        store = Store(os.path.join(tmpdir(), "nope.json"))
        self.assertEqual(store.section("orders"), {})

    def test_save_writes_atomically_and_reloads(self):
        path = os.path.join(tmpdir(), "store.json")
        store = Store(path)
        store.section("products")["A"] = {"name": "a", "unit_cents": 1}
        store.save()
        self.assertEqual(json.load(open(path))["products"]["A"]["unit_cents"], 1)
        self.assertFalse([n for n in os.listdir(os.path.dirname(path)) if n.startswith(".store-")])
        self.assertEqual(Store(path).section("products")["A"]["name"], "a")

    def test_unknown_section_is_an_error(self):
        with self.assertRaises(KeyError):
            Store(os.path.join(tmpdir(), "s.json")).section("wallets")
