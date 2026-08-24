from pathlib import Path

import yaml

from app.services.country_policy import resolve_country_policy


def test_every_configured_country_pack_has_an_explicit_runtime_policy():
    packs = []
    for path in sorted(Path('config/countries').glob('*.yaml')):
        payload = yaml.safe_load(path.read_text(encoding='utf-8'))
        packs.append(payload)
        policy = resolve_country_policy(payload['country_code'])
        assert policy.country == payload['country_code']

    assert {item['country_code'] for item in packs} == {'US', 'GB', 'BR'}


def test_disabled_country_packs_remain_commercially_fail_closed():
    for path in sorted(Path('config/countries').glob('*.yaml')):
        payload = yaml.safe_load(path.read_text(encoding='utf-8'))
        if payload['enabled']:
            continue
        policy = resolve_country_policy(payload['country_code'])
        assert payload['features']['outbound'] is False
        assert policy.commercial_outbound_allowed is False
        assert policy.paid_social_allowed is False
        assert policy.route_mode == 'informational_only'
