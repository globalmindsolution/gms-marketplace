# HTTP API

All bodies are JSON. Money is integer cents.

| Method | Path | Response |
|---|---|---|
| GET | `/health` | `200 {"status": "ok"}` |
| GET | `/orders/<id>` | `200` the order plus its `quote` for today; `404` when unknown |
| POST | `/orders` | `201` the created draft order; `400` on a malformed body; `409` when stock is short |

`POST /orders` body:

```json
{"customer_id": "c1", "items": [{"sku": "MUG", "quantity": 2}], "coupon": "TEN"}
```

The quote has `subtotal`, `discount`, `tax` and `total`. Confirming and paying
an order are CLI operations today (`orders order`, `orders pay`); the API is
read-and-create only.
