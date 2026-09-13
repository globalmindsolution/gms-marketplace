"""Shared fixtures: a store in a temp dir with two products and some stock."""

import os
import tempfile
from datetime import date

TODAY = date(2026, 6, 15)


def settings(tmp, tax_rate=0.20):
    from orders.config import Settings
    return Settings(currency="EUR", tax_rate=tax_rate,
                    store_path=os.path.join(tmp, "store.json"), gateway_timeout_s=1.0)


def service_in(tmp, tax_rate=0.20):
    # Imported here so this module loads on every commit of the fixture's
    # history, including the ones before these modules existed.
    from orders.discounts import Coupon, CouponBook
    from orders.inventory import Inventory
    from orders.orders import OrderService
    from orders.payments.gateway import Gateway
    from orders.storage import Store
    st = settings(tmp, tax_rate)
    store = Store(st.store_path)
    store.section("products")["MUG"] = {"name": "Mug", "unit_cents": 1250}
    store.section("products")["TEE"] = {"name": "T-shirt", "unit_cents": 2000}
    inv = Inventory(store)
    inv.receive("MUG", 10)
    inv.receive("TEE", 5)
    coupons = CouponBook()
    coupons.add(Coupon("TEN", percent=10))
    coupons.add(Coupon("FIVER", fixed_cents=500, valid_from=date(2026, 6, 1), valid_to=date(2026, 6, 30)))
    return store, OrderService(store, inv, Gateway(store), st, coupons)


def tmpdir():
    return tempfile.mkdtemp(prefix="orders-test-")
