"""Coupon codes: a percentage or a fixed amount, valid inside a date window."""

from dataclasses import dataclass
from datetime import date


@dataclass(frozen=True)
class Coupon:
    code: str
    percent: int = 0
    fixed_cents: int = 0
    valid_from: date = date.min
    valid_to: date = date.max

    def __post_init__(self):
        if self.percent and self.fixed_cents:
            raise ValueError("a coupon is a percentage or a fixed amount, not both")
        if not 0 <= self.percent <= 100:
            raise ValueError("percent must be between 0 and 100")

    def active_on(self, day):
        return self.valid_from <= day <= self.valid_to

    def discount_cents(self, subtotal_cents):
        """The reduction this coupon takes off `subtotal_cents`, never below zero."""
        if self.percent:
            return subtotal_cents * self.percent // 100
        return min(self.fixed_cents, subtotal_cents)


class CouponBook:
    def __init__(self):
        self._by_code = {}

    def add(self, coupon):
        self._by_code[coupon.code.upper()] = coupon

    def lookup(self, code, day):
        coupon = self._by_code.get((code or "").upper())
        if coupon is None or not coupon.active_on(day):
            return None
        return coupon
