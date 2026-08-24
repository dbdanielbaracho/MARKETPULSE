from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime, timezone
from urllib.parse import urlparse

from app.services.pro_billing import OfficialStripeGateway, StripeGateway
from app.storage.api_accounts import ApiCustomerStore, ApiSubscriptionEntitlement


class ApiBillingConfigurationError(RuntimeError):
    pass


@dataclass(frozen=True)
class ApiPlanConfig:
    plan: str
    product_id: str
    price_id: str
    daily_limit: int
    scopes: tuple[str, ...]


@dataclass(frozen=True)
class ApiBillingConfig:
    secret_key: str
    webhook_secret: str
    public_base_url: str

    @classmethod
    def from_env(cls) -> "ApiBillingConfig":
        secret = os.getenv("MP_STRIPE_SECRET_KEY", "").strip()
        webhook = os.getenv("MP_STRIPE_WEBHOOK_SECRET", "").strip()
        origin = os.getenv("MP_PUBLIC_BASE_URL", "https://predibeacon.com").strip().rstrip("/")
        if not secret or not webhook:
            raise ApiBillingConfigurationError("Commercial API Stripe billing is not configured")
        parsed = urlparse(origin)
        if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password or parsed.path not in ("", "/") or parsed.query or parsed.fragment:
            raise ApiBillingConfigurationError("MP_PUBLIC_BASE_URL must be an origin-only HTTPS URL")
        return cls(secret, webhook, origin)


_ALLOWED_SCOPES = frozenset({"markets:read", "history:read"})
_PLANS = ("starter", "pro", "business")


def api_plan_catalog() -> dict[str, ApiPlanConfig]:
    """Load only explicitly configured plans; never invent product economics or quotas."""
    catalog: dict[str, ApiPlanConfig] = {}
    for plan in _PLANS:
        prefix = f"MP_API_{plan.upper()}"
        product_id = os.getenv(f"{prefix}_PRODUCT_ID", "").strip()
        price_id = os.getenv(f"MP_STRIPE_API_{plan.upper()}_PRICE_ID", "").strip()
        limit_raw = os.getenv(f"{prefix}_DAILY_LIMIT", "").strip()
        scopes_raw = os.getenv(f"{prefix}_SCOPES", "").strip()
        supplied = (product_id, price_id, limit_raw, scopes_raw)
        if not any(supplied):
            continue
        if not all(supplied):
            raise ApiBillingConfigurationError(f"Commercial API {plan} plan configuration is incomplete")
        if len(product_id) > 255 or any(ch.isspace() for ch in product_id) or len(price_id) > 255 or any(ch.isspace() for ch in price_id):
            raise ApiBillingConfigurationError(f"Commercial API {plan} provider identifiers are invalid")
        try:
            daily_limit = int(limit_raw)
        except ValueError as exc:
            raise ApiBillingConfigurationError(f"Commercial API {plan} daily limit must be an integer") from exc
        if daily_limit < 1 or daily_limit > 1_000_000:
            raise ApiBillingConfigurationError(f"Commercial API {plan} daily limit is out of bounds")
        scopes = tuple(sorted({part.strip() for part in scopes_raw.split(",") if part.strip()}))
        if not scopes or any(scope not in _ALLOWED_SCOPES for scope in scopes):
            raise ApiBillingConfigurationError(f"Commercial API {plan} scopes are invalid")
        catalog[plan] = ApiPlanConfig(plan, product_id, price_id, daily_limit, scopes)
    return catalog


def _provider_url(value: str) -> str:
    parsed = urlparse(value)
    host = (parsed.hostname or "").casefold()
    if parsed.scheme != "https" or not host or not (host == "stripe.com" or host.endswith(".stripe.com")):
        raise ApiBillingConfigurationError("billing provider returned an unexpected redirect URL")
    return value


def create_api_checkout(
    *, account_id: str,
    email: str,
    plan: ApiPlanConfig,
    config: ApiBillingConfig,
    gateway: StripeGateway | None = None,
) -> str:
    if not account_id.startswith("apiacct_") or "@" not in email:
        raise ValueError("invalid Commercial API checkout identity")
    gateway = gateway or OfficialStripeGateway(config.secret_key)
    session = gateway.create_checkout(
        mode="subscription",
        line_items=[{"price": plan.price_id, "quantity": 1}],
        customer_email=email,
        client_reference_id=account_id,
        success_url=f"{config.public_base_url}/?api_billing=success",
        cancel_url=f"{config.public_base_url}/?api_billing=cancelled",
        allow_promotion_codes=False,
    )
    return _provider_url(str(session.url))


def create_api_portal(*, customer_id: str, config: ApiBillingConfig, gateway: StripeGateway | None = None) -> str:
    if not customer_id.startswith("cus_"):
        raise ValueError("invalid Stripe customer id")
    gateway = gateway or OfficialStripeGateway(config.secret_key)
    session = gateway.create_portal(customer=customer_id, return_url=f"{config.public_base_url}/")
    return _provider_url(str(session.url))


def verify_api_webhook(*, payload: bytes, signature: str, config: ApiBillingConfig, gateway: StripeGateway | None = None):
    if not signature.strip():
        raise ValueError("Stripe-Signature header is required")
    gateway = gateway or OfficialStripeGateway(config.secret_key)
    return gateway.construct_event(payload, signature, config.webhook_secret)


def _mapping(value: object) -> Mapping[str, object]:
    if isinstance(value, Mapping):
        return value
    converter = getattr(value, "to_dict_recursive", None)
    if callable(converter):
        converted = converter()
        if isinstance(converted, Mapping):
            return converted
    raise ValueError("Stripe event object must be a mapping")


def _provider_id(value: object, prefix: str) -> str:
    if isinstance(value, Mapping):
        value = value.get("id")
    if not isinstance(value, str) or not value.startswith(prefix) or len(value) > 255:
        raise ValueError("invalid provider identifier")
    return value


def _subscription_plan(subscription: Mapping[str, object], catalog: dict[str, ApiPlanConfig]) -> tuple[ApiPlanConfig, datetime | None] | None:
    items = subscription.get("items")
    data = items.get("data") if isinstance(items, Mapping) else None
    if not isinstance(data, list) or not data:
        raise ValueError("subscription items are required")
    by_product = {item.product_id: item for item in catalog.values()}
    matches: list[tuple[ApiPlanConfig, int | None]] = []
    for raw in data:
        if not isinstance(raw, Mapping):
            continue
        price = raw.get("price")
        if not isinstance(price, Mapping):
            continue
        product = price.get("product")
        if isinstance(product, Mapping):
            product = product.get("id")
        plan = by_product.get(str(product))
        if plan:
            period = raw.get("current_period_end")
            matches.append((plan, period if isinstance(period, int) and not isinstance(period, bool) and period > 0 else None))
    unique = {match[0].plan for match in matches}
    if not matches:
        return None
    if len(unique) != 1:
        raise ValueError("subscription contains multiple configured Commercial API plans")
    plan = matches[0][0]
    periods = [period for _, period in matches if period is not None]
    valid_until = datetime.fromtimestamp(min(periods), tz=timezone.utc) if periods else None
    return plan, valid_until


def process_api_subscription_event(event: object, *, store: ApiCustomerStore, catalog: dict[str, ApiPlanConfig]) -> str:
    payload = _mapping(event)
    event_id = _provider_id(payload.get("id"), "evt_")
    event_type = payload.get("type")
    if not isinstance(event_type, str) or not event_type or len(event_type) > 160:
        raise ValueError("invalid provider event type")
    if store.event_seen(event_id):
        return "duplicate"
    data = payload.get("data")
    if not isinstance(data, Mapping):
        raise ValueError("provider event data is required")
    obj = _mapping(data.get("object"))
    if event_type == "checkout.session.completed":
        if obj.get("mode") != "subscription":
            store.mark_event_once(event_id, event_type)
            return "ignored_non_subscription_checkout"
        account_id = obj.get("client_reference_id")
        if not isinstance(account_id, str):
            raise ValueError("checkout missing internal account reference")
        store.bind_customer(account_id, _provider_id(obj.get("customer"), "cus_"))
        store.mark_event_once(event_id, event_type)
        return "customer_bound"
    if event_type not in {"customer.subscription.created", "customer.subscription.updated", "customer.subscription.deleted"}:
        store.mark_event_once(event_id, event_type)
        return "ignored_event_type"
    account = store.by_customer(_provider_id(obj.get("customer"), "cus_"))
    if account is None:
        raise LookupError("billing customer is not bound to a Commercial API account")
    matched = _subscription_plan(obj, catalog)
    if matched is None:
        store.mark_event_once(event_id, event_type)
        return "ignored_other_product"
    plan, valid_until = matched
    status = obj.get("status")
    if not isinstance(status, str) or not status or len(status) > 80:
        raise ValueError("subscription status is required")
    if event_type == "customer.subscription.deleted":
        status = "canceled"
    store.upsert_entitlement(
        ApiSubscriptionEntitlement(
            account_id=account.account_id,
            plan=plan.plan,
            product_id=plan.product_id,
            subscription_id=_provider_id(obj.get("id"), "sub_"),
            status=status.casefold(),
            valid_until=valid_until,
        )
    )
    store.mark_event_once(event_id, event_type)
    return "entitlement_projected"


def active_api_plan(store: ApiCustomerStore, account_id: str, catalog: dict[str, ApiPlanConfig] | None = None) -> ApiPlanConfig | None:
    catalog = catalog if catalog is not None else api_plan_catalog()
    entitlement = store.entitlement(account_id)
    if entitlement is None or not entitlement.grants_access():
        return None
    plan = catalog.get(entitlement.plan)
    if plan is None or plan.product_id != entitlement.product_id:
        return None
    return plan
