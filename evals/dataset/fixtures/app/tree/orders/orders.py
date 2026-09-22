"""The order life cycle: draft -> confirmed -> paid, or -> cancelled from any of them."""

import uuid

from .models import Order, OrderLine
from .pricing import quote

TRANSITIONS = {
    "draft": {"confirmed", "cancelled"},
    "confirmed": {"paid", "cancelled"},
    "paid": {"cancelled"},
    "cancelled": set(),
}


class InvalidTransition(Exception):
    pass


class OrderService:
    def __init__(self, store, inventory, gateway, settings, coupons=None):
        self.orders = store.section("orders")
        self.products = store.section("products")
        self.inventory = inventory
        self.gateway = gateway
        self.settings = settings
        self.coupons = coupons

    def create(self, customer_id, items, coupon=""):
        """items: list of (sku, quantity). Reserves stock up front."""
        lines = []
        for sku, quantity in items:
            product = self.products.get(sku)
            if product is None:
                raise KeyError("unknown sku %s" % sku)
            self.inventory.reserve(sku, quantity)
            lines.append(OrderLine(sku=sku, quantity=quantity, unit_cents=int(product["unit_cents"])))
        order = Order(id=uuid.uuid4().hex[:12], customer_id=customer_id, lines=lines, coupon=coupon)
        self.orders[order.id] = order.to_dict()
        return order

    def get(self, order_id):
        data = self.orders.get(order_id)
        if data is None:
            raise KeyError("no order %s" % order_id)
        return Order.from_dict(data)

    def _move(self, order, status):
        if status not in TRANSITIONS[order.status]:
            raise InvalidTransition("%s -> %s" % (order.status, status))
        order.status = status
        self.orders[order.id] = order.to_dict()
        return order

    def quote(self, order, day):
        coupon = self.coupons.lookup(order.coupon, day) if self.coupons and order.coupon else None
        return quote(order.lines, self.settings.tax_rate, coupon)

    def confirm(self, order_id):
        return self._move(self.get(order_id), "confirmed")

    def pay(self, order_id, day):
        order = self.get(order_id)
        if order.status != "confirmed":
            raise InvalidTransition("%s -> paid" % order.status)
        total = self.quote(order, day)["total"]
        charge = self.gateway.charge(order.id, total)
        order.charge_id = charge["id"]
        return self._move(order, "paid")

    def cancel(self, order_id):
        order = self._move(self.get(order_id), "cancelled")
        for line in order.lines:
            self.inventory.release(line.sku, line.quantity)
        return order
