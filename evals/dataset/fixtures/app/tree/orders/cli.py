"""Command line: seed products, receive stock, place and pay orders, report."""

import argparse
import sys
from datetime import date

from .config import load
from .discounts import CouponBook
from .inventory import Inventory
from .orders import OrderService
from .payments.gateway import Gateway
from .reports import render, summary
from .storage import Store


def build_service(settings):
    store = Store(settings.store_path)
    service = OrderService(store, Inventory(store), Gateway(store), settings, CouponBook())
    return store, service


def main(argv=None):
    ap = argparse.ArgumentParser(prog="orders")
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("product"); p.add_argument("sku"); p.add_argument("name"); p.add_argument("unit_cents", type=int)
    r = sub.add_parser("receive"); r.add_argument("sku"); r.add_argument("quantity", type=int)
    o = sub.add_parser("order"); o.add_argument("customer"); o.add_argument("items", nargs="+", help="sku:qty")
    pay = sub.add_parser("pay"); pay.add_argument("order_id")
    sub.add_parser("report")
    args = ap.parse_args(argv)

    settings = load()
    store, service = build_service(settings)
    if args.cmd == "product":
        store.section("products")[args.sku] = {"name": args.name, "unit_cents": args.unit_cents}
    elif args.cmd == "receive":
        service.inventory.receive(args.sku, args.quantity)
    elif args.cmd == "order":
        items = [(part.split(":")[0], int(part.split(":")[1])) for part in args.items]
        order = service.create(args.customer, items)
        service.confirm(order.id)
        print(order.id)
    elif args.cmd == "pay":
        order = service.pay(args.order_id, date.today())
        print(order.status)
    elif args.cmd == "report":
        print(render(summary(store.section("charges")), settings.currency))
    store.save()
    return 0


if __name__ == "__main__":
    sys.exit(main())
