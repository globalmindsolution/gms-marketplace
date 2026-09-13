"""A minimal JSON HTTP API on http.server: GET /health, GET /orders/<id>, POST /orders."""

import json
from http.server import BaseHTTPRequestHandler, HTTPServer


def make_handler(service, day_provider):
    class Handler(BaseHTTPRequestHandler):
        def _send(self, status, body):
            payload = json.dumps(body).encode()
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)

        def do_GET(self):
            if self.path == "/health":
                return self._send(200, {"status": "ok"})
            if self.path.startswith("/orders/"):
                order_id = self.path[len("/orders/"):]
                try:
                    order = service.get(order_id)
                except KeyError:
                    return self._send(404, {"error": "no such order"})
                body = order.to_dict()
                body["quote"] = service.quote(order, day_provider())
                return self._send(200, body)
            return self._send(404, {"error": "not found"})

        def do_POST(self):
            if self.path != "/orders":
                return self._send(404, {"error": "not found"})
            length = int(self.headers.get("Content-Length") or 0)
            try:
                payload = json.loads(self.rfile.read(length) or b"{}")
                items = [(i["sku"], int(i["quantity"])) for i in payload["items"]]
                order = service.create(payload["customer_id"], items, payload.get("coupon", ""))
            except (KeyError, ValueError, TypeError) as exc:
                return self._send(400, {"error": str(exc)})
            except Exception as exc:  # noqa: BLE001 - stock errors surface as 409
                return self._send(409, {"error": str(exc)})
            return self._send(201, order.to_dict())

        def log_message(self, *_args):
            return

    return Handler


def serve(service, day_provider, host="127.0.0.1", port=0):
    return HTTPServer((host, port), make_handler(service, day_provider))
