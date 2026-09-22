import json
import threading
import unittest
import urllib.error
import urllib.request

from orders.api import serve
from tests._support import TODAY, service_in, tmpdir


class ApiTest(unittest.TestCase):
    def setUp(self):
        _store, self.svc = service_in(tmpdir())
        self.server = serve(self.svc, lambda: TODAY)
        self.base = "http://127.0.0.1:%d" % self.server.server_address[1]
        threading.Thread(target=self.server.serve_forever, daemon=True).start()

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()

    def _get(self, path):
        try:
            with urllib.request.urlopen(self.base + path) as r:
                return r.status, json.loads(r.read())
        except urllib.error.HTTPError as e:
            return e.code, json.loads(e.read())

    def _post(self, path, body):
        req = urllib.request.Request(self.base + path, data=json.dumps(body).encode(),
                                     headers={"Content-Type": "application/json"}, method="POST")
        try:
            with urllib.request.urlopen(req) as r:
                return r.status, json.loads(r.read())
        except urllib.error.HTTPError as e:
            return e.code, json.loads(e.read())

    def test_health(self):
        self.assertEqual(self._get("/health"), (200, {"status": "ok"}))

    def test_create_then_fetch_with_quote(self):
        status, created = self._post("/orders", {"customer_id": "c1", "items": [{"sku": "MUG", "quantity": 2}], "coupon": "TEN"})
        self.assertEqual(status, 201)
        status, body = self._get("/orders/" + created["id"])
        self.assertEqual(status, 200)
        self.assertEqual(body["quote"]["total"], 2700)

    def test_bad_payload_is_400_and_stock_conflict_is_409(self):
        self.assertEqual(self._post("/orders", {"customer_id": "c1"})[0], 400)
        self.assertEqual(self._post("/orders", {"customer_id": "c1", "items": [{"sku": "TEE", "quantity": 99}]})[0], 409)

    def test_unknown_routes(self):
        self.assertEqual(self._get("/orders/nope")[0], 404)
        self.assertEqual(self._get("/nothing")[0], 404)
        self.assertEqual(self._post("/nothing", {})[0], 404)
