"""Stock levels with reservation; a reservation is the only way stock leaves."""


class OutOfStock(Exception):
    pass


class Inventory:
    def __init__(self, store):
        self.stock = store.section("stock")

    def level(self, sku):
        return int(self.stock.get(sku, 0))

    def receive(self, sku, quantity):
        if quantity <= 0:
            raise ValueError("received quantity must be positive")
        self.stock[sku] = self.level(sku) + quantity
        return self.stock[sku]

    def reserve(self, sku, quantity):
        available = self.level(sku)
        if quantity > available:
            raise OutOfStock("%s: wanted %d, have %d" % (sku, quantity, available))
        self.stock[sku] = available - quantity
        return self.stock[sku]

    def release(self, sku, quantity):
        self.stock[sku] = self.level(sku) + quantity
        return self.stock[sku]
