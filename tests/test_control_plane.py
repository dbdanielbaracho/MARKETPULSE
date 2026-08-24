from copy import deepcopy

import pytest

from app.services.runtime_control import append_tracking, configured_provider, effective_provider
from app.storage.control_plane import ControlPlaneStore, DEFAULT_CONTROL_PLANE, validate_control_plane


def test_control_plane_draft_does_not_change_published(tmp_path):
    path = str(tmp_path / "db.sqlite")
    store = ControlPlaneStore(path)
    payload = deepcopy(DEFAULT_CONTROL_PLANE)
    payload["providers"]["kalshi_us"]["partner_id"] = "partner-1234"
    payload["providers"]["kalshi_us"]["commercial_verified"] = True
    payload["providers"]["kalshi_us"]["tracking_parameter"] = "ref"
    payload["providers"]["kalshi_us"]["tracking_value"] = "abc"

    saved = store.save_draft(payload, "tester")
    assert saved["draft"]["providers"]["kalshi_us"]["partner_id"] == "partner-1234"
    assert saved["published"]["providers"]["kalshi_us"]["partner_id"] == ""


def test_control_plane_publish_is_immediately_effective(tmp_path):
    path = str(tmp_path / "db.sqlite")
    store = ControlPlaneStore(path)
    payload = deepcopy(DEFAULT_CONTROL_PLANE)
    payload["providers"]["kalshi_us"].update({
        "partner_id": "partner-live",
        "commercial_verified": True,
        "tracking_parameter": "ref",
        "tracking_value": "live-code",
    })
    store.save_draft(payload, "tester")
    result = store.publish("tester")

    provider = effective_provider(path, "kalshi")
    assert result["published_version"] == 1
    assert provider.provider_key == "kalshi_us"
    assert provider.commercial_verified is True
    assert provider.attribution_id == "partner-live"
    assert append_tracking("https://kalshi.com/markets/example", provider).endswith("?ref=live-code")


def test_control_plane_rollback_creates_new_published_version(tmp_path):
    path = str(tmp_path / "db.sqlite")
    store = ControlPlaneStore(path)
    first = deepcopy(DEFAULT_CONTROL_PLANE)
    first["providers"]["kalshi_us"]["enabled"] = False
    store.save_draft(first, "tester")
    store.publish("tester")

    second = deepcopy(first)
    second["providers"]["kalshi_us"]["enabled"] = True
    store.save_draft(second, "tester")
    store.publish("tester")

    rolled = store.rollback(1, "tester")
    assert rolled["published_version"] == 3
    assert rolled["published"]["providers"]["kalshi_us"]["enabled"] is False


def test_control_plane_rejects_verified_provider_without_identifier():
    payload = deepcopy(DEFAULT_CONTROL_PLANE)
    payload["providers"]["kalshi_us"]["commercial_verified"] = True
    with pytest.raises(ValueError, match="commercial_verified"):
        validate_control_plane(payload)


def test_country_allow_and_block_rules(tmp_path):
    provider = effective_provider(str(tmp_path / "db.sqlite"), "kalshi")
    assert provider.country_allowed("US") is True
    assert provider.country_allowed("BR") is False

    polymarket = effective_provider(str(tmp_path / "db2.sqlite"), "polymarket")
    assert polymarket.provider_key == "polymarket_intl"
    assert polymarket.country_allowed("BR") is False
    assert polymarket.country_allowed("US") is False
    assert polymarket.country_allowed("ES") is True

    polymarket_us = configured_provider(str(tmp_path / "db3.sqlite"), "polymarket_us")
    assert polymarket_us.enabled is False
    assert polymarket_us.country_allowed("US") is True
    assert polymarket_us.country_allowed("BR") is False


def test_first_control_plane_shape_migrates_without_losing_existing_values():
    legacy = deepcopy(DEFAULT_CONTROL_PLANE)
    legacy["providers"] = {
        "kalshi": deepcopy(DEFAULT_CONTROL_PLANE["providers"]["kalshi_us"]),
        "polymarket": deepcopy(DEFAULT_CONTROL_PLANE["providers"]["polymarket_intl"]),
    }
    legacy["providers"]["kalshi"]["partner_id"] = "legacy-id"
    normalized = validate_control_plane(legacy)
    assert normalized["providers"]["kalshi_us"]["partner_id"] == "legacy-id"
    assert "polymarket_us" in normalized["providers"]
