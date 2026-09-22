# Architecture

`orders` is a single process over one JSON document. Requests enter through
the HTTP API or the CLI, pass through `OrderService`, and touch the store
through three collaborators: inventory, pricing and the payment gateway.

| Module | Responsibility |
|---|---|
| `orders/config.py` | Settings from the environment (currency, tax rate, store path, gateway timeout). |
| `orders/models.py` | Frozen records; money is integer cents. |
| `orders/storage.py` | The JSON document, written atomically. |
| `orders/inventory.py` | Stock levels; reservation is the only way stock leaves. |
| `orders/discounts.py` | Coupons: percentage or fixed, inside a date window. |
| `orders/pricing.py` | Subtotal → coupon → tax (half-up on the cent) → total. |
| `orders/orders.py` | The order life cycle: draft → confirmed → paid, cancel from any state. |
| `orders/payments/gateway.py` | Charges with idempotency keys; refunds against a charge. |
| `orders/payments/refunds.py` | Refund policy: full for 14 days, restocking fee to 90 days, nothing after. |
| `orders/reports.py` | Revenue summary over the charge ledger. |
| `orders/api.py` | JSON HTTP API (`/health`, `/orders`). |
| `orders/cli.py` | Command line over the same service. |

## Data flow for a paid order

1. `POST /orders` (or `orders order`) → `OrderService.create` reserves stock
   and stores a `draft` order.
2. `confirm` moves it to `confirmed`.
3. `pay` quotes the order (coupon before tax), charges the gateway with an
   idempotency key derived from the order id and amount, records the charge id
   on the order and moves it to `paid`.
4. `cancel` from any state releases the reserved stock; a paid order's money is
   returned through `refunds.refund_order`, which applies the policy and then
   the gateway.

## Invariants

- Money is integer cents end to end; tax rounds half up on the cent.
- A charge for the same order and amount is made at most once.
- Stock never goes negative: a reservation that would is refused before any
  state changes.
