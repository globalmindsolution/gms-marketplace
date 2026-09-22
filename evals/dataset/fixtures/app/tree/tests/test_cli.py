import io
import os
import unittest
from contextlib import redirect_stdout
from unittest import mock

from orders import cli
from tests._support import tmpdir


class CliTest(unittest.TestCase):
    def test_end_to_end_through_the_cli(self):
        store = os.path.join(tmpdir(), "store.json")
        env = {"ORDERS_STORE": store, "ORDERS_TAX_RATE": "0.10", "ORDERS_CURRENCY": "USD"}
        with mock.patch.dict(os.environ, env, clear=False):
            self.assertEqual(cli.main(["product", "MUG", "Mug", "1000"]), 0)
            self.assertEqual(cli.main(["receive", "MUG", "5"]), 0)
            out = io.StringIO()
            with redirect_stdout(out):
                cli.main(["order", "c1", "MUG:2"])
            order_id = out.getvalue().strip()
            out = io.StringIO()
            with redirect_stdout(out):
                cli.main(["pay", order_id])
            self.assertEqual(out.getvalue().strip(), "paid")
            out = io.StringIO()
            with redirect_stdout(out):
                cli.main(["report"])
            self.assertIn("net:      22.00 USD", out.getvalue())
