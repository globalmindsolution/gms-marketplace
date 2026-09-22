# orders

A small order-management service: products, stock, pricing with coupons,
orders with a confirm/cancel life cycle, payments through an idempotent
gateway, refunds, a daily revenue report, a JSON HTTP API and a CLI. Pure
Python standard library; state lives in one JSON file.

    make test        # unit tests
    make coverage    # coverage gate (fail-under in .coveragerc)
    python3 -m orders.cli --help

See `docs/` for the architecture, the API and the decision records.
