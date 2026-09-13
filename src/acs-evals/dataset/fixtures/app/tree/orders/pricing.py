"""Totals in integer cents: subtotal, coupon, then tax on the discounted amount."""


def line_total(line):
    return line.unit_cents * line.quantity


def subtotal(lines):
    return sum(line_total(line) for line in lines)


def tax_cents(amount_cents, tax_rate):
    """Round half up on the cent, so 0.5 cents becomes one cent, not zero."""
    scaled = amount_cents * tax_rate * 100
    return int((scaled + 50) // 100)


def quote(lines, tax_rate, coupon=None):
    """A breakdown dict; the coupon is applied before tax."""
    sub = subtotal(lines)
    discount = coupon.discount_cents(sub) if coupon is not None else 0
    taxable = sub - discount
    tax = tax_cents(taxable, tax_rate)
    return {"subtotal": sub, "discount": discount, "tax": tax,
            "total": taxable + tax}
