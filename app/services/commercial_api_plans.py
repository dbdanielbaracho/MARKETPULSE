from __future__ import annotations

import os
import re
from dataclasses import dataclass

_PLAN_NAMES = ("starter", "pro", "business")
_ALLOWED_SCOPES = frozenset({"markets:read", "history:read"})
_PROVIDER_ID = re.compile(r"^(?:prod|price)_[A-Za-z0-9_:-]{3,200}$")


@dataclass(frozen=True)
class CommercialApiPlan:
    name: str
    product_id: str
    price_id: str
    scopes: tuple[str, ...]
    daily_limit: int


@dataclass(frozen=True)
class CommercialApiPlanCatalog:
    plans: tuple[CommercialApiPlan, ...]

    @classmethod
    def from_env(cls) -> "CommercialApiPlanCatalog":
        plans: list[CommercialApiPlan] = []
        product_ids: set[str] = set()
        price_ids: set[str] = set()
        for name in _PLAN_NAMES:
            prefix = f"MP_API_{name.upper()}"
            product = os.getenv(f"{prefix}_PRODUCT_ID", "").strip()
            price = os.getenv(f"{prefix}_PRICE_ID", "").strip()
            scopes_raw = os.getenv(f"{prefix}_SCOPES", "").strip()
            limit_raw = os.getenv(f"{prefix}_DAILY_LIMIT", "").strip()
            values = (product, price, scopes_raw, limit_raw)
            if not any(values):
                continue
            if not all(values):
                raise ValueError(f"incomplete commercial API plan configuration: {name}")
            if not _PROVIDER_ID.fullmatch(product) or not product.startswith("prod_"):
                raise ValueError(f"invalid commercial API Product ID: {name}")
            if not _PROVIDER_ID.fullmatch(price) or not price.startswith("price_"):
                raise ValueError(f"invalid commercial API Price ID: {name}")
            scopes = tuple(sorted({item.strip() for item in scopes_raw.split(",") if item.strip()}))
            if not scopes or any(scope not in _ALLOWED_SCOPES for scope in scopes):
                raise ValueError(f"invalid commercial API scopes: {name}")
            try:
                daily_limit = int(limit_raw)
            except ValueError as exc:
                raise ValueError(f"invalid commercial API daily limit: {name}") from exc
            if daily_limit < 1 or daily_limit > 1_000_000:
                raise ValueError(f"commercial API daily limit out of bounds: {name}")
            if product in product_ids or price in price_ids:
                raise ValueError("commercial API Product/Price IDs must be unique across plans")
            product_ids.add(product)
            price_ids.add(price)
            plans.append(CommercialApiPlan(name, product, price, scopes, daily_limit))
        return cls(tuple(plans))

    def by_name(self, name: str) -> CommercialApiPlan | None:
        normalized = name.strip().casefold()
        return next((plan for plan in self.plans if plan.name == normalized), None)

    def by_product(self, product_id: str) -> CommercialApiPlan | None:
        return next((plan for plan in self.plans if plan.product_id == product_id), None)

    def public_inventory(self) -> list[dict[str, object]]:
        return [
            {
                "name": name,
                "available": self.by_name(name) is not None,
                "scopes": list(self.by_name(name).scopes) if self.by_name(name) else [],
                "daily_limit": self.by_name(name).daily_limit if self.by_name(name) else None,
            }
            for name in _PLAN_NAMES
        ]
