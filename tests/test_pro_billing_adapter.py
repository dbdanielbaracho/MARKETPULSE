from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.services.pro_billing import (
    BillingConfig,
    BillingConfigurationError,
    create_checkout_session,
    create_customer_portal_session,
    verify_webhook,
)


class FakeGateway:
    def __init__(self, *, checkout_url="https://checkout.stripe.com/c/pay/cs_test_123", portal_url="https://billing.stripe.com/p/session/test_123"):
        self.checkout_url = checkout_url
        self.portal_url = portal_url
        self.checkout_params = None
        self.portal_params = None
        self.webhook_args = None

    def create_checkout(self, **params):
        self.checkout_params = params
        return SimpleNamespace(url=self.checkout_url, id="cs_test_123")

    def create_portal(self, **params):
        self.portal_params = params
        return SimpleNamespace(url=self.portal_url, id="bps_test_123")

    def construct_event(self, payload, signature, secret):
        self.webhook_args = (payload, signature, secret)
        return {"id": "evt_123", "type": "customer.subscription.updated"}


def config() -> BillingConfig:
    return BillingConfig(
        secret_key="sk_test_not_real",
        pro_price_id="price_test_not_real",
        webhook_secret="whsec_test_not_real",
        public_base_url="https://predibeacon.com",
    )


def test_billing_config_fails_closed_without_required_values(monkeypatch):
    for name in ("MP_STRIPE_SECRET_KEY", "MP_STRIPE_PRO_PRICE_ID", "MP_STRIPE_WEBHOOK_SECRET"):
        monkeypatch.delenv(name, raising=False)
    with pytest.raises(BillingConfigurationError, match="missing billing configuration"):
        BillingConfig.from_env()


def test_billing_config_requires_https_public_origin(monkeypatch):
    monkeypatch.setenv("MP_STRIPE_SECRET_KEY", "sk_test_x")
    monkeypatch.setenv("MP_STRIPE_PRO_PRICE_ID", "price_x")
    monkeypatch.setenv("MP_STRIPE_WEBHOOK_SECRET", "whsec_x")
    monkeypatch.setenv("MP_PUBLIC_BASE_URL", "http://predibeacon.com")
    with pytest.raises(BillingConfigurationError, match="absolute https URL"):
        BillingConfig.from_env()


def test_checkout_is_hosted_subscription_and_uses_internal_reference():
    gateway = FakeGateway()
    redirect = create_checkout_session(
        account_ref="acct_internal_123",
        customer_email="customer@example.com",
        config=config(),
        gateway=gateway,
    )
    assert redirect.url.startswith("https://checkout.stripe.com/")
    assert redirect.provider_session_id == "cs_test_123"
    assert gateway.checkout_params["mode"] == "subscription"
    assert gateway.checkout_params["line_items"] == [{"price": "price_test_not_real", "quantity": 1}]
    assert gateway.checkout_params["client_reference_id"] == "acct_internal_123"
    assert gateway.checkout_params["success_url"].startswith("https://predibeacon.com/")
    assert gateway.checkout_params["cancel_url"] == "https://predibeacon.com/pro"


def test_checkout_rejects_untrusted_provider_redirect():
    gateway = FakeGateway(checkout_url="https://evil.example/steal")
    with pytest.raises(BillingConfigurationError, match="unexpected redirect URL"):
        create_checkout_session(
            account_ref="acct_1",
            customer_email="customer@example.com",
            config=config(),
            gateway=gateway,
        )


def test_portal_requires_stripe_customer_identity_and_provider_host():
    gateway = FakeGateway()
    redirect = create_customer_portal_session(
        stripe_customer_id="cus_123",
        config=config(),
        gateway=gateway,
    )
    assert redirect.url.startswith("https://billing.stripe.com/")
    assert gateway.portal_params == {
        "customer": "cus_123",
        "return_url": "https://predibeacon.com/pro",
    }
    with pytest.raises(ValueError, match="invalid Stripe customer id"):
        create_customer_portal_session(stripe_customer_id="not-a-customer", config=config(), gateway=gateway)


def test_webhook_requires_signature_and_delegates_to_official_verifier_boundary():
    gateway = FakeGateway()
    with pytest.raises(ValueError, match="Stripe-Signature"):
        verify_webhook(payload=b"{}", signature="", config=config(), gateway=gateway)
    event = verify_webhook(payload=b"{}", signature="t=1,v1=sig", config=config(), gateway=gateway)
    assert event["id"] == "evt_123"
    assert gateway.webhook_args == (b"{}", "t=1,v1=sig", "whsec_test_not_real")


def test_adapter_does_not_put_internal_commercial_data_in_public_redirect_urls():
    gateway = FakeGateway()
    redirect = create_checkout_session(
        account_ref="acct_private_999",
        customer_email="customer@example.com",
        config=config(),
        gateway=gateway,
    )
    lowered = redirect.url.casefold()
    for forbidden in ("commission", "partner_id", "revenue_share", "price_test_not_real", "acct_private_999"):
        assert forbidden not in lowered
