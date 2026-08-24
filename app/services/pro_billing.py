from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Protocol
from urllib.parse import urlparse

import stripe


class BillingConfigurationError(RuntimeError):
    pass


@dataclass(frozen=True)
class BillingConfig:
    secret_key: str
    pro_price_id: str
    webhook_secret: str
    public_base_url: str

    @classmethod
    def from_env(cls) -> "BillingConfig":
        secret_key = os.getenv("MP_STRIPE_SECRET_KEY", "").strip()
        price_id = os.getenv("MP_STRIPE_PRO_PRICE_ID", "").strip()
        webhook_secret = os.getenv("MP_STRIPE_WEBHOOK_SECRET", "").strip()
        public_base_url = os.getenv("MP_PUBLIC_BASE_URL", "https://predibeacon.com").strip().rstrip("/")
        missing = [
            name
            for name, value in (
                ("MP_STRIPE_SECRET_KEY", secret_key),
                ("MP_STRIPE_PRO_PRICE_ID", price_id),
                ("MP_STRIPE_WEBHOOK_SECRET", webhook_secret),
            )
            if not value
        ]
        if missing:
            raise BillingConfigurationError(f"missing billing configuration: {', '.join(missing)}")
        parsed = urlparse(public_base_url)
        if parsed.scheme != "https" or not parsed.netloc:
            raise BillingConfigurationError("MP_PUBLIC_BASE_URL must be an absolute https URL")
        return cls(secret_key, price_id, webhook_secret, public_base_url)


class StripeGateway(Protocol):
    def create_checkout(self, **params): ...
    def create_portal(self, **params): ...
    def construct_event(self, payload: bytes, signature: str, secret: str): ...


class OfficialStripeGateway:
    def __init__(self, api_key: str) -> None:
        stripe.api_key = api_key

    def create_checkout(self, **params):
        return stripe.checkout.Session.create(**params)

    def create_portal(self, **params):
        return stripe.billing_portal.Session.create(**params)

    def construct_event(self, payload: bytes, signature: str, secret: str):
        return stripe.Webhook.construct_event(payload, signature, secret)


@dataclass(frozen=True)
class BillingRedirect:
    url: str
    provider_session_id: str


def _https_provider_url(value: str, *, expected_host_suffix: str) -> str:
    parsed = urlparse(value)
    host = (parsed.hostname or "").casefold()
    suffix = expected_host_suffix.casefold()
    if parsed.scheme != "https" or not host or not (host == suffix or host.endswith("." + suffix)):
        raise BillingConfigurationError("billing provider returned an unexpected redirect URL")
    return value


def create_checkout_session(
    *,
    account_ref: str,
    customer_email: str,
    config: BillingConfig,
    stripe_customer_id: str | None = None,
    gateway: StripeGateway | None = None,
) -> BillingRedirect:
    """Create a hosted subscription checkout from authenticated server-side identity."""
    account_ref = account_ref.strip()
    customer_email = customer_email.strip()
    if not account_ref:
        raise ValueError("account_ref is required")
    if "@" not in customer_email or len(customer_email) > 254:
        raise ValueError("valid customer_email is required")
    if stripe_customer_id is not None:
        stripe_customer_id = stripe_customer_id.strip()
        if not stripe_customer_id.startswith("cus_") or len(stripe_customer_id) > 255:
            raise ValueError("invalid Stripe customer id")

    gateway = gateway or OfficialStripeGateway(config.secret_key)
    params = {
        "mode": "subscription",
        "line_items": [{"price": config.pro_price_id, "quantity": 1}],
        "client_reference_id": account_ref,
        "success_url": f"{config.public_base_url}/pro/success?session_id={{CHECKOUT_SESSION_ID}}",
        "cancel_url": f"{config.public_base_url}/pro",
        "allow_promotion_codes": False,
    }
    if stripe_customer_id is None:
        params["customer_email"] = customer_email
    else:
        params["customer"] = stripe_customer_id
    session = gateway.create_checkout(**params)
    url = _https_provider_url(str(session.url), expected_host_suffix="stripe.com")
    return BillingRedirect(url=url, provider_session_id=str(session.id))


def create_customer_portal_session(
    *,
    stripe_customer_id: str,
    config: BillingConfig,
    gateway: StripeGateway | None = None,
) -> BillingRedirect:
    stripe_customer_id = stripe_customer_id.strip()
    if not stripe_customer_id.startswith("cus_"):
        raise ValueError("invalid Stripe customer id")
    gateway = gateway or OfficialStripeGateway(config.secret_key)
    session = gateway.create_portal(
        customer=stripe_customer_id,
        return_url=f"{config.public_base_url}/pro",
    )
    url = _https_provider_url(str(session.url), expected_host_suffix="stripe.com")
    return BillingRedirect(url=url, provider_session_id=str(session.id))


def verify_webhook(*, payload: bytes, signature: str, config: BillingConfig, gateway: StripeGateway | None = None):
    if not signature.strip():
        raise ValueError("Stripe-Signature header is required")
    gateway = gateway or OfficialStripeGateway(config.secret_key)
    return gateway.construct_event(payload, signature, config.webhook_secret)
