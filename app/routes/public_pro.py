from __future__ import annotations

import os

from fastapi import APIRouter

from app.domain.pro import PRO_PACKAGE
from app.services.pro_entitlements import ProProductConfig

router = APIRouter()


def _billing_ready() -> bool:
    required = (
        "MP_STRIPE_SECRET_KEY",
        "MP_STRIPE_PRO_PRICE_ID",
        "MP_STRIPE_WEBHOOK_SECRET",
    )
    return all(os.getenv(name, "").strip() for name in required)


def _checkout_ready() -> bool:
    if not _billing_ready():
        return False
    try:
        return ProProductConfig.from_env() is not None
    except ValueError:
        return False


@router.get("/api/v1/pro/package")
def pro_package() -> dict[str, object]:
    """Public product capabilities only; never returns secrets, IDs or invented prices."""
    return {
        "code": PRO_PACKAGE.code,
        "name": PRO_PACKAGE.name,
        "features": [feature.value for feature in PRO_PACKAGE.features],
        "billing_available": _billing_ready(),
        "checkout_available": _checkout_ready(),
    }
