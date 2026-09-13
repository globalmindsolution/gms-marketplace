"""Domain records. Money is integer cents everywhere; floats never touch a total."""

from dataclasses import dataclass, field, asdict
from typing import List


@dataclass(frozen=True)
class Product:
    sku: str
    name: str
    unit_cents: int

    def __post_init__(self):
        if self.unit_cents < 0:
            raise ValueError("unit price cannot be negative")


@dataclass(frozen=True)
class Customer:
    id: str
    email: str


@dataclass(frozen=True)
class OrderLine:
    sku: str
    quantity: int
    unit_cents: int

    def __post_init__(self):
        if self.quantity <= 0:
            raise ValueError("quantity must be positive")


@dataclass
class Order:
    id: str
    customer_id: str
    lines: List[OrderLine] = field(default_factory=list)
    status: str = "draft"
    coupon: str = ""
    charge_id: str = ""

    def to_dict(self):
        return asdict(self)

    @classmethod
    def from_dict(cls, data):
        lines = [OrderLine(**line) for line in data.get("lines", [])]
        return cls(id=data["id"], customer_id=data["customer_id"], lines=lines,
                   status=data.get("status", "draft"), coupon=data.get("coupon", ""),
                   charge_id=data.get("charge_id", ""))
