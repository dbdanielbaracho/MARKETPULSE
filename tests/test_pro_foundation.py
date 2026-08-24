from app.domain.pro import PRO_PACKAGE, ProFeature, has_entitlement
from app.routes.public_pro import _billing_ready, _checkout_ready, pro_package


def test_pro_access_is_explicit_entitlement_only():
    assert has_entitlement({"advanced_alerts"}, ProFeature.ADVANCED_ALERTS) is True
    assert has_entitlement(set(), ProFeature.ADVANCED_ALERTS) is False
    assert has_entitlement({"pro"}, ProFeature.ADVANCED_ALERTS) is False


def test_pro_package_has_stable_feature_keys():
    assert PRO_PACKAGE.code == "pro"
    assert {feature.value for feature in PRO_PACKAGE.features} == {
        "advanced_alerts", "extended_history", "advanced_signals", "exports"
    }


def test_billing_readiness_fails_closed_without_provider_config(monkeypatch):
    for name in ("MP_STRIPE_SECRET_KEY", "MP_STRIPE_PRO_PRICE_ID", "MP_STRIPE_WEBHOOK_SECRET", "MP_PRO_PRODUCT_ID"):
        monkeypatch.delenv(name, raising=False)
    assert _billing_ready() is False
    assert _checkout_ready() is False
    payload = pro_package()
    assert payload["billing_available"] is False
    assert payload["checkout_available"] is False


def test_checkout_requires_billing_and_product_identity_without_exposing_them(monkeypatch):
    monkeypatch.setenv("MP_STRIPE_SECRET_KEY", "sk_test_private")
    monkeypatch.setenv("MP_STRIPE_PRO_PRICE_ID", "price_private")
    monkeypatch.setenv("MP_STRIPE_WEBHOOK_SECRET", "whsec_private")
    monkeypatch.delenv("MP_PRO_PRODUCT_ID", raising=False)
    payload = pro_package()
    assert payload["billing_available"] is True
    assert payload["checkout_available"] is False

    monkeypatch.setenv("MP_PRO_PRODUCT_ID", "prod_private")
    payload = pro_package()
    serialized = repr(payload)
    assert payload["billing_available"] is True
    assert payload["checkout_available"] is True
    for forbidden in ("sk_test_private", "price_private", "whsec_private", "prod_private", "commission"):
        assert forbidden.casefold() not in serialized.casefold()


def test_invalid_product_configuration_keeps_checkout_fail_closed(monkeypatch):
    monkeypatch.setenv("MP_STRIPE_SECRET_KEY", "sk_test_private")
    monkeypatch.setenv("MP_STRIPE_PRO_PRICE_ID", "price_private")
    monkeypatch.setenv("MP_STRIPE_WEBHOOK_SECRET", "whsec_private")
    monkeypatch.setenv("MP_PRO_PRODUCT_ID", "bad product id")
    assert _billing_ready() is True
    assert _checkout_ready() is False
    assert pro_package()["checkout_available"] is False
