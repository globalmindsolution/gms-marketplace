"""Runtime settings, read from the environment with safe defaults."""

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    currency: str
    tax_rate: float
    store_path: str
    gateway_timeout_s: float


def load(env=None):
    """Build Settings from `env` (default: os.environ); malformed numbers fail loudly."""
    env = os.environ if env is None else env
    return Settings(
        currency=env.get("ORDERS_CURRENCY", "EUR"),
        tax_rate=float(env.get("ORDERS_TAX_RATE", "0.20")),
        store_path=env.get("ORDERS_STORE", "data/store.json"),
        gateway_timeout_s=float(env.get("ORDERS_GATEWAY_TIMEOUT", "5.0")),
    )
