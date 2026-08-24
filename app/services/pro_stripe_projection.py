from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime, timezone

from app.services.pro_entitlements import ProEntitlementStore, ProProductConfig, ProviderEntitlementState
from app.storage.pro_accounts import ProAccountStore

_SUBSCRIPTION_EVENTS = frozenset({
    "customer.subscription.created",
    "customer.subscription.updated",
    "customer.subscription.deleted",
})


def _mapping(value: object) -> Mapping[str, object]:
    if isinstance(value, Mapping):
        return value
    converter = getattr(value, "to_dict_recursive", None)
    if callable(converter):
        converted = converter()
        if isinstance(converted, Mapping):
            return converted
    raise ValueError("Stripe event object must be a mapping")


def _id(value: object, prefix: str) -> str:
    if isinstance(value, Mapping):
        value = value.get("id")
    if not isinstance(value, str) or not value.startswith(prefix) or len(value) > 255:
        raise ValueError(f"invalid provider {prefix.rstrip('_')} identifier")
    return value


def _matching_product_period_end(subscription: Mapping[str, object], product_id: str) -> datetime | None:
    items = subscription.get("items")
    if not isinstance(items, Mapping):
        raise ValueError("subscription items are required")
    data = items.get("data")
    if not isinstance(data, list) or not data:
        raise ValueError("subscription items are required")
    matching_periods: list[int] = []
    matched = False
    for raw_item in data:
        if not isinstance(raw_item, Mapping):
            continue
        price = raw_item.get("price")
        if not isinstance(price, Mapping):
            continue
        raw_product = price.get("product")
        if isinstance(raw_product, Mapping):
            raw_product = raw_product.get("id")
        if raw_product != product_id:
            continue
        matched = True
        period_end = raw_item.get("current_period_end")
        if isinstance(period_end, int) and not isinstance(period_end, bool) and period_end > 0:
            matching_periods.append(period_end)
    if not matched:
        raise LookupError("subscription does not contain configured Pro product")
    if not matching_periods:
        return None
    return datetime.fromtimestamp(min(matching_periods), tz=timezone.utc)


def process_verified_subscription_event(
    event: object,
    *,
    accounts: ProAccountStore,
    entitlements: ProEntitlementStore,
    product: ProProductConfig,
) -> str:
    payload = _mapping(event)
    event_id = _id(payload.get("id"), "evt_")
    event_type = payload.get("type")
    if not isinstance(event_type, str) or not event_type or len(event_type) > 160:
        raise ValueError("invalid provider event type")
    if accounts.event_seen(event_id):
        return "duplicate"
    data = payload.get("data")
    if not isinstance(data, Mapping):
        raise ValueError("provider event data is required")
    obj = _mapping(data.get("object"))

    if event_type == "checkout.session.completed":
        if obj.get("mode") != "subscription":
            accounts.mark_event_once(event_id, event_type)
            return "ignored_non_subscription_checkout"
        account_id = obj.get("client_reference_id")
        if not isinstance(account_id, str):
            raise ValueError("subscription checkout missing internal account reference")
        customer_id = _id(obj.get("customer"), "cus_")
        accounts.bind_customer(account_id, customer_id)
        accounts.mark_event_once(event_id, event_type)
        return "customer_bound"

    if event_type not in _SUBSCRIPTION_EVENTS:
        accounts.mark_event_once(event_id, event_type)
        return "ignored_event_type"

    customer_id = _id(obj.get("customer"), "cus_")
    account = accounts.by_customer(customer_id)
    if account is None:
        raise LookupError("provider customer is not bound to an active PrediBeacon Pro account")
    subscription_id = _id(obj.get("id"), "sub_")
    status = obj.get("status")
    if not isinstance(status, str) or not status or len(status) > 80:
        raise ValueError("subscription status is required")
    try:
        valid_until = _matching_product_period_end(obj, product.product_id)
    except LookupError:
        accounts.mark_event_once(event_id, event_type)
        return "ignored_other_product"
    if event_type == "customer.subscription.deleted":
        status = "canceled"
    entitlements.upsert_provider_state(
        ProviderEntitlementState(
            subject_id=account.account_id,
            product_id=product.product_id,
            subscription_id=subscription_id,
            status=status.casefold(),
            valid_until=valid_until,
        )
    )
    accounts.mark_event_once(event_id, event_type)
    return "entitlement_projected"
